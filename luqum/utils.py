# -*- coding: utf-8 -*-
"""Various utilities for dealing with syntax trees.

Include base classes to implement a visitor pattern.

"""
from .tree import BaseOperation, OrOperation, AndOperation


def camel_to_lower(name):
    return "".join(
        "_" + w.lower() if w.isupper() else w.lower()
        for w in name).lstrip("_")


class LuceneTreeVisitor:
    """
    Tree Visitor base class, inspired by python's :class:`ast.NodeVisitor`.

    This class is meant to be subclassed, with the subclass implementing
    visitor methods for each Node type it is interested in.

    By default, those visitor method should be named ``'visit_'`` + class
    name of the node, converted to lower_case (ie: visit_search_node for a
    SearchNode class).

    You can tweak this behaviour by overriding the `visitor_method_prefix` &
    `generic_visitor_method_name` class attributes.

    If the goal is to modify the initial tree,
    use :py:class:`LuceneTreeTranformer` instead.
    """
    visitor_method_prefix = 'visit_'
    generic_visitor_method_name = 'generic_visit'

    _get_method_cache = None

    def _get_method(self, node):
        if self._get_method_cache is None:
            self._get_method_cache = {}
        try:
            meth = self._get_method_cache[type(node)]
        except KeyError:
            for cls in node.__class__.mro():
                try:
                    method_name = "{}{}".format(
                        self.visitor_method_prefix,
                        camel_to_lower(cls.__name__)
                    )
                    meth = getattr(self, method_name)
                    break
                except AttributeError:
                    continue
            else:
                meth = getattr(self, self.generic_visitor_method_name)
            self._get_method_cache[type(node)] = meth
        return meth

    def visit(self, node, parents=[]):
        """ Basic, recursive traversal of the tree. """
        method = self._get_method(node)
        yield from method(node, parents)
        for child in node.children:
            yield from self.visit(child, parents + [node])

    def generic_visit(self, node, parents=[]):
        """
        Default visitor function, called if nothing matches the current node.
        """
        return iter([])     # No-op


class LuceneTreeTransformer(LuceneTreeVisitor):
    """
    A :class:`LuceneTreeVisitor` subclass that walks the abstract syntax tree
    and allows modifications of traversed nodes.

    The `LuceneTreeTransormer` will walk the AST and use the return value of the
    visitor methods to replace or remove the old node. If the return value of
    the visitor method is ``None``, the node will be removed from its location,
    otherwise it is replaced with the return value. The return value may be the
    original node, in which case no replacement takes place.
    """
    def replace_node(self, old_node, new_node, parent):
        for k, v in parent.__dict__.items():
            if v == old_node:
                parent.__dict__[k] = new_node
                break
            elif isinstance(v, list):
                try:
                    i = v.index(old_node)
                    v[i] = new_node
                    break
                except ValueError:
                    pass
            elif isinstance(v, tuple):
                try:
                    i = v.index(old_node)
                    v = list(v)
                    v[i] = new_node
                    parent.__dict__[k] = tuple(v)
                    break
                except ValueError:
                    pass

    def generic_visit(self, node, parent=[]):
        return node

    def visit(self, node, parents=[]):
        """
        Recursively traverses the tree and replace nodes with the appropriate
        visitor method's return values.
        """
        method = self._get_method(node)
        new_node = method(node, parents)
        if parents:
            self.replace_node(node, new_node, parents[-1])
        node = new_node
        for child in node.children:
            self.visit(child, parents + [node])
        return node


class LuceneTreeVisitorV2(LuceneTreeVisitor):
    """
    V2 of the LuceneTreeVisitor allowing to evaluate the AST

    It differs from py:cls:`LuceneTreeVisitor`
    because it's up to the visit method to recursively call children (or not)

    This class is meant to be subclassed, with the subclass implementing
    visitor methods for each Node type it is interested in.

    By default, those visitor method should be named ``'visit_'`` + class
    name of the node, converted to lower_case (ie: visit_search_node for a
    SearchNode class).

    You can tweak this behaviour by overriding the `visitor_method_prefix` &
    `generic_visitor_method_name` class attributes.

    If the goal is to modify the initial tree,
    use :py:class:`LuceneTreeTranformer` instead.
    """

    def visit(self, node, parents=None, context=None):
        """ Basic, recursive traversal of the tree.

        :param list parents: the list of parents
        :parma dict context: a dict of contextual variable for free use
          to track states while traversing the tree
        """
        if parents is None:
            parents = []

        method = self._get_method(node)
        return method(node, parents, context)

    def generic_visit(self, node, parents=None, context=None):
        """
        Default visitor function, called if nothing matches the current node.
        """
        raise AttributeError(
            "No visitor found for this type of node: {}".format(
                node.__class__
            )
        )


class UnknownOperationResolver(LuceneTreeTransformer):
    """Transform the UnknownOperation to OR or AND
    """

    VALID_OPERATIONS = frozenset([None, AndOperation, OrOperation])
    DEFAULT_OPERATION = AndOperation

    def __init__(self, resolve_to=None):
        """Initialize a new resolver

        :param resolve_to: must be either None, OrOperation or AndOperation.

          for the latter two the UnknownOperation is repalced by specified operation.

          if it is None, we use the last operation encountered, as would Lucene do
        """
        if resolve_to not in self.VALID_OPERATIONS:
            raise ValueError("%r is not a valid value for resolve_to" % resolve_to)
        self.resolve_to = resolve_to
        self.last_operation = {}

    def _first_nonop_parent(self, parents):
        for parent in parents:
            if not isinstance(parent, BaseOperation):
                return id(parent)  # use id() because parent might not be hashable
        return None

    def visit_or_operation(self, node, parents=None):
        if self.resolve_to is None:
            # memorize last op
            parent = self._first_nonop_parent(parents)
            self.last_operation[parent] = OrOperation
        return node

    def visit_and_operation(self, node, parents=None):
        if self.resolve_to is None:
            # memorize last op
            parent = self._first_nonop_parent(parents)
            self.last_operation[parent] = AndOperation
        return node

    def visit_unknown_operation(self, node, parents=None):
        # resolve
        if self.resolve_to is None:
            parent = self._first_nonop_parent(parents)
            operation = self.last_operation.get(parent, None)
            if operation is None:
                operation = self.DEFAULT_OPERATION
        else:
            operation = self.resolve_to
        return operation(*node.operands)

    def __call__(self, tree):
        return self.visit(tree)


def normalize_nested_fields_specs(nested_fields):
    """normalize nested_fields specification to only have nested dicts

    :param dict nested_fields:  dict contains fields that are nested in ES
        each nested fields contains either
        a dict of nested fields
        (if some of them are also nested)
        or a list of nesdted fields (this is for commodity)
    """
    if nested_fields is None:
        return {}
    elif isinstance(nested_fields, dict):
        return {k: normalize_nested_fields_specs(v) for k, v in nested_fields.items()}
    else:
        # should be an iterable, transform to dict
        return {sub: {} for sub in nested_fields}
