from luqum.elasticsearch.tree import ElasticSearchItemFactory
from .tree import (
    EMust, EMustNot, EShould, EWord, AbstractEItem, EPhrase, ERange)
from ..utils import LuceneTreeVisitorV2


class ElasticsearchQueryBuilder(LuceneTreeVisitorV2):
    """
    TODO write some doc
    """

    SHOULD = 'should'
    MUST = 'must'

    def __init__(self, default_operator=SHOULD, default_field='text',
                 not_analyzed_fields=None):

        if not_analyzed_fields:
            self._not_analyzed_fields = not_analyzed_fields
        else:
            self._not_analyzed_fields = []

        self.default_operator = default_operator
        self.default_field = default_field
        self.es_item_factory = ElasticSearchItemFactory(
            no_analyze=self._not_analyzed_fields
        )

    def simplify_if_same(self, children, current_node):
        """
        If two same operation are nested, then simplify
        Should be use only with should and must operations because Not(Not(x))
        can't be simplified as Not(x)
        :param children:
        :param current_node:
        :return:
        """
        for child in children:
            if type(child) is type(current_node):
                yield from self.simplify_if_same(child.children, current_node)
            else:
                yield child

    def _must_operation(self, node, parents):
        items = [self.visit(n, parents + [node])
                 for n in self.simplify_if_same(node.children, node)]
        return self.es_item_factory.build(EMust, items)

    def _should_operation(self, node, parents):
        items = [self.visit(n, parents + [node])
                 for n in self.simplify_if_same(node.children, node)]
        return self.es_item_factory.build(EShould, items)

    def visit_and_operation(self, *args, **kwargs):
        return self._must_operation(*args, **kwargs)

    def visit_or_operation(self, *args, **kwargs):
        return self._should_operation(*args, **kwargs)

    def visit_word(self, node, parents):
        return self.es_item_factory.build(
            EWord,
            value=node.value,
            field=self.default_field
        )

    def _set_search_field_in_all_children(self, node, field_name):
        if isinstance(node, AbstractEItem):
            node.field = field_name
        else:
            for item in node.items:
                self._set_search_field_in_all_children(item, field_name)

    def visit_search_field(self, node, parents):
        enode = self.visit(node.children[0], parents + [node])
        self._set_search_field_in_all_children(enode, node.name)
        return enode

    def visit_not(self, node, parents):
        items = [self.visit(n, parents + [node])
                 for n in self.simplify_if_same(node.children, node)]
        return self.es_item_factory.build(EMustNot, items)

    def visit_prohibit(self, *args, **kwargs):
        return self.visit_not(*args, **kwargs)

    def visit_plus(self, *args, **kwargs):
        return self._must_operation(*args, **kwargs)

    def visit_unknown_operation(self, *args, **kwargs):
        if self.default_operator == self.SHOULD:
            return self._should_operation(*args, **kwargs)
        elif self.default_operator == self.MUST:
            return self._must_operation(*args, **kwargs)

    def visit_boost(self, node, parents):
        eword = self.visit(node.children[0], parents + [node])
        eword.boost = float(node.force)
        return eword

    def visit_fuzzy(self, node, parents):
        eword = self.visit(node.term, parents + [node])
        eword.fuzziness = float(node.degree)
        return eword

    def visit_proximity(self, node, parents):
        ephrase = self.visit(node.term, parents + [node])
        ephrase.slop = float(node.degree)
        return ephrase

    def visit_phrase(self, node, parents):
        return self.es_item_factory.build(
            EPhrase,
            phrase=node.value,
            field=self.default_field
        )

    def visit_range(self, node, parents):
        kwargs = {
            'gte' if node.include_low else 'gt': node.low.value,
            'lte' if node.include_high else 'lt': node.high.value,
        }
        return self.es_item_factory.build(ERange, **kwargs)

    def visit_group(self, node, parents):
        return self.visit(node.expr, parents + [node])

    def visit_field_group(self, node, parents):
        fields = self.visit(node.expr, parents + [node])
        return fields
