from luqum.elasticsearch.tree import ElasticSearchItemFactory
from luqum.exceptions import OrAndAndOnSameLevel
from luqum.tree import (
    OrOperation, AndOperation, UnknownOperation, SearchField)
from luqum.tree import Word  # noqa: F401
from .tree import (
    EMust, EMustNot, EShould, EWord, AbstractEItem, EPhrase, ERange,
    ENested)
from ..utils import LuceneTreeVisitorV2, normalize_nested_fields_specs
from ..check import CheckNestedFields


class ElasticsearchQueryBuilder(LuceneTreeVisitorV2):
    """
    Query builder to convert a Tree in an Elasticsearch query dsl (json)

    .. warning:: there are some limitations

        - mix of AND and OR on same level in expressions is not supported
          has this leads to unpredictable results (see `this article`_)

        - for full text fields,
          `zero_terms_query` parameter of `match queries`_
          is managed at best according to where the terms appears.
          Lucene would just remove fields with only stop words
          while this query builder have to retain all expressions,
          even if is only made of stop words.
          So in the case of an expression appearing in `AND` expression,
          it will be set to "all"
          while it will be set to "none" if it's part of a `OR` on `AND NOT`
          to avoid influencing the rest of the query.
          Some edge case like having all terms resolving to stop words
          may however lead to different results than string_query..

    .. _`this article`: https://lucidworks.com/blog/2011/12/28/why-not-and-or-and-not/
    .. _`match queries`:
        https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-match-query.html
    """

    SHOULD = 'should'
    MUST = 'must'

    def __init__(self, default_operator=SHOULD, default_field='text',
                 not_analyzed_fields=None, nested_fields=None):
        """
        :param default_operator: to replace blank operator (MUST or SHOULD)
        :param default_field: to search
        :param not_analyzed_fields: field that are not analyzed in ES
        :param nested_fields: dict contains fields that are nested in ES
            each nested fields contains
            either a dict of nested fields
            (if some of them are also nested)
            or a list of nesdted fields (this is for commodity)
        """

        if not_analyzed_fields:
            self._not_analyzed_fields = not_analyzed_fields
        else:
            self._not_analyzed_fields = []

        self.nested_fields = self._normalize_nested_fields(nested_fields)

        self.default_operator = default_operator
        self.default_field = default_field
        self.es_item_factory = ElasticSearchItemFactory(
            no_analyze=self._not_analyzed_fields,
            nested_fields=self.nested_fields
        )

    def _normalize_nested_fields(self, nested_fields):
        return normalize_nested_fields_specs(nested_fields)

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
        child_str_1 = str(binary_operation.children[0])
        child_str_2 = str(binary_operation.children[1])
        middle_length = len(node_str) - len(child_str_1) - len(child_str_2)
        position = node_str.find(child_str_2)
        if position - middle_length - delta >= 0:
            start = position - middle_length - delta
        else:
            start = 0
        end = position + delta
        return node_str[start:end]

    def _is_must(self, operation):
        """
        Returns True if the node is a AndOperation or an UnknownOperation when
        the default operator is MUST
        :param node: to check
        :return: Boolean

        >>> ElasticsearchQueryBuilder(
        ...     default_operator=ElasticsearchQueryBuilder.MUST
        ... )._is_must(AndOperation(Word('Monty'), Word('Python')))
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
        >>> ElasticsearchQueryBuilder(
        ...     default_operator=ElasticsearchQueryBuilder.MUST
        ... )._is_should(OrOperation(Word('Monty'), Word('Python')))
        True
        """
        return (
            isinstance(operation, OrOperation) or
            isinstance(operation, UnknownOperation) and
            self.default_operator == ElasticsearchQueryBuilder.SHOULD
        )

    def _yield_nested_children(self, parent, children):
        """
        Raise if a OR (should) is in a AND (must) without being in parenthesis

        >>> builder = ElasticsearchQueryBuilder()
        >>> op = OrOperation(Word('yo'), OrOperation(Word('lo'), Word('py')))
        >>> list(builder._yield_nested_children(op, op.children))
        [Word('yo'), OrOperation(Word('lo'), Word('py'))]


        >>> op = OrOperation(Word('yo'), AndOperation(Word('lo'), Word('py')))
        >>> list(builder._yield_nested_children(op, op.children))
        Traceback (most recent call last):
            ...
        luqum.exceptions.OrAndAndOnSameLevel: lo AND py
        """

        for child in children:
            if (self._is_should(parent) and self._is_must(child) or
               self._is_must(parent) and self._is_should(child)):
                raise OrAndAndOnSameLevel(
                    self._get_operator_extract(child)
                )
            else:
                yield child

    def _binary_operation(self, cls, node, parents, context):
        children = self.simplify_if_same(node.children, node)
        children = self._yield_nested_children(node, children)
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

    def visit_word(self, node, parents, context):
        return self.es_item_factory.build(
            EWord,
            q=node.value,
            default_field=self.default_field
        )

    def _set_fields_in_all_children(self, enode, field_name):
        """
        Recursive method to set the field name even in nested enode.
        For instance in this case: field:(spam OR eggs OR (monthy AND python))
        """
        if isinstance(enode, AbstractEItem):
            enode.add_field(field_name)
        elif isinstance(enode, ENested):
            nested_path_to_add = field_name.split('.' + enode.nested_path)[0]
            enode.add_nested_path(nested_path_to_add)
            self._set_fields_in_all_children(enode.items, field_name)
        else:
            for item in enode.items:
                self._set_fields_in_all_children(item, field_name)

    def _is_nested(self, node):
        if isinstance(node, SearchField) and '.' in node.name:
            return True

        for child in node.children:
            if isinstance(child, SearchField):
                return True
            elif self._is_nested(child):
                return True

        return False

    def _create_nested(self, node_name, items):

        nested_path = node_name
        if '.' in node_name:
            # reverse the list
            nesteds_path = node_name.split('.')[::-1]
            # the first is the search field not a path
            nested_path = nesteds_path.pop(1)

        enode = self.es_item_factory.build(
            ENested, nested_path=nested_path, items=items)

        # if this is a paht with point(s) in it
        if nested_path != node_name and len(nesteds_path) > 1:
            node_name = '.'.join(nesteds_path)
            return self._create_nested(node_name, enode)

        return enode

    def visit_search_field(self, node, parents, context):
        enode = self.visit(node.children[0], parents + [node])
        if self._is_nested(node):
            enode = self._create_nested(node_name=node.name, items=enode)
            self._set_fields_in_all_children(enode.items, node.name)
        else:
            self._set_fields_in_all_children(enode, node.name)

        return enode

    def visit_not(self, node, parents, context):
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

    def visit_boost(self, node, parents, context):
        eword = self.visit(node.children[0], parents + [node])
        eword.boost = float(node.force)
        return eword

    def visit_fuzzy(self, node, parents, context):
        eword = self.visit(node.term, parents + [node])
        eword.fuzziness = float(node.degree)
        return eword

    def visit_proximity(self, node, parents, context):
        ephrase = self.visit(node.term, parents + [node])
        ephrase.slop = float(node.degree)
        return ephrase

    def visit_phrase(self, node, parents, context):
        return self.es_item_factory.build(
            EPhrase,
            phrase=node.value,
            default_field=self.default_field
        )

    def visit_range(self, node, parents, context):
        kwargs = {
            'gte' if node.include_low else 'gt': node.low.value,
            'lte' if node.include_high else 'lt': node.high.value,
        }
        return self.es_item_factory.build(ERange, **kwargs)

    def visit_group(self, node, parents, context):
        return self.visit(node.expr, parents + [node])

    def visit_field_group(self, node, parents, context):
        fields = self.visit(node.expr, parents + [node])
        return fields

    def __call__(self, tree):
        """Calling the query builder returns
        you the json compatible structure corresponding to the request tree passed in parameter

        :param luqum.tree.Item tree: a luqum parse tree
        :return dict:
        """
        CheckNestedFields(nested_fields=self.nested_fields)(tree)
        return self.visit(tree).json
