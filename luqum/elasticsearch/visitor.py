from luqum.elasticsearch.tree import ElasticSearchItemFactory
from luqum.tree import (
    OrOperation, AndOperation, UnknownOperation, SearchField, Word)
from .tree import (
    EMust, EMustNot, EShould, EWord, AbstractEItem, EPhrase, ERange)
from ..utils import LuceneTreeVisitorV2


class OrAndAndOnSameLevel(Exception):
    pass


class NestedSearchFieldException(Exception):
    pass


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

    def _get_operator_extract(self, binary_operation, delta=8):
        """
        Return an extract around the operator
        :param binary_operation: operator to extract
        :param delta: nb of characters to extract before and after the operator
        :return: str

        >>> operation = OrOperation(Word('Python'), Word('Monty'))
        >>> builder = ElasticsearchQueryBuilder()
        >>> builder._get_operator_extract(operation, 3)
        'hon OR Mon'
        """
        node_str = str(binary_operation)
        first_child_str = str(binary_operation.children[0])
        second_child_str = str(binary_operation.children[1])
        middle_length = len(node_str) - len(first_child_str) - len(second_child_str)
        position = node_str.find(second_child_str)
        start = position - middle_length - delta if position - middle_length - delta >= 0 else 0
        end = position + delta
        return node_str[start:end]

    def _is_must(self, operation):
        """
        Returns True if the node is a AndOperation or an UnknownOperation when
        the default operator is MUST
        :param node: to check
        :return: Boolean

        >>> builder = ElasticsearchQueryBuilder(\
                default_operator=ElasticsearchQueryBuilder.MUST)
        >>> builder._is_must(AndOperation(Word('Monty'), Word('Python')))
        True
        """
        return (
            isinstance(operation, AndOperation) or
            isinstance(operation, UnknownOperation) and
            self.default_operator == ElasticsearchQueryBuilder.MUST
        )

    def _is_should(self, operation):
        """
        Returns True if the node is a OrOperation or an UnknownOperation when
        the default operator is SHOULD
        >>> builder = ElasticsearchQueryBuilder(\
                default_operator=ElasticsearchQueryBuilder.MUST)
        >>> builder._is_should(OrOperation(Word('Monty'), Word('Python')))
        True
        """
        return (
            isinstance(operation, OrOperation) or
            isinstance(operation, UnknownOperation) and
            self.default_operator == ElasticsearchQueryBuilder.SHOULD
        )

    def _raise_if_children_not_same(self, parent, children):

        for child in children:
            if (self._is_should(parent) and self._is_must(child) or
               self._is_must(parent) and self._is_should(child)):
                raise OrAndAndOnSameLevel(
                    self._get_operator_extract(child)
                )
            else:
                yield child

    def _raise_if_nested_search_field(self, node):
        for child in node.children:
            if isinstance(child, SearchField):
                raise NestedSearchFieldException(str(child))
            else:
                self._raise_if_nested_search_field(child)

    def _binary_operation(self, cls, node, parents):
        children = self.simplify_if_same(node.children, node)
        children = self._raise_if_children_not_same(node, children)
        items = [self.visit(child, parents + [node]) for child in children]
        return self.es_item_factory.build(cls, items)

    def _must_operation(self, *args, **kwargs):
        return self._binary_operation(EMust, *args, **kwargs)

    def _should_operation(self, *args, **kwargs):
        return self._binary_operation(EShould, *args, **kwargs)

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
        self._raise_if_nested_search_field(node)
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
