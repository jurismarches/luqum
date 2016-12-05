# -*- coding: utf-8 -*-
"""Various utilities for dealing with syntax trees.

Include base classes to implement a visitor pattern.

"""

from .exceptions import NestedSearchFieldException


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

    def generic_visit(self, node, parent=[]):
        return node

    def visit(self, node, parents=[]):
        """
        Recursively traverses the tree and replace nodes with the appropriate
        visitor methid's return values.
        """
        method = self._get_method(node)
        new_node = method(node, parents)
        if parents:
            self.replace_node(node, new_node, parents[-1])
        else:
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


class CheckLuceneTreeVisitor(LuceneTreeVisitorV2):
    """
    Visit the lucene tree to make some checks

    In particular to check nested fields.

    :param nested_fields: a dict where keys are name of nested fields,
        values are dict of sub-nested fields or an empty dict for leaf
    """

    def __init__(self, nested_fields):
        assert(isinstance(nested_fields, dict))
        self.nested_fields = nested_fields

    def generic_visit(self, node, parents, context):
        """
        If nothing matches the current node, visit children
        """
        for child in node.children:
            self.visit(child, parents + [node], context)

    def _recurse_nested_fields(self, node, context, parents):
        names = node.name.split(".")
        nested_fields = context["nested_fields"]
        current_field = context["current_field"]
        for name in names:
            if name in nested_fields:
                # recurse
                nested_fields = nested_fields[name]
                current_field = name
            elif current_field is not None:  # we are inside another field
                if nested_fields:
                    # calling an unknown field inside a nested one
                    raise NestedSearchFieldException(
                        '"{sub}" is not a subfield of "{field}" in "{expr}"'
                        .format(sub=name, field=current_field, expr=str(parents[-1])))
                else:
                    # calling a field inside a non nested
                    raise NestedSearchFieldException(
                        '''"{sub}" can't be nested in "{field}" in "{expr}"'''
                        .format(sub=name, field=current_field, expr=str(parents[-1])))
            else:
                # not a nested field, so no nesting any more
                nested_fields = {}
                current_field = name
        return {"nested_fields": nested_fields, "current_field": current_field}

    def visit_search_field(self, node, parents, context):
        """
        On search field node, check nested fields logic
        """
        context = dict(context)  # copy
        context.update(self._recurse_nested_fields(node, context, parents))
        for child in node.children:
            self.visit(child, parents + [node], context)

    def visit_term(self, node, parents, context):
        """
        On term field, verify term is in a final search field
        """
        if context["nested_fields"] and context["current_field"]:
            raise NestedSearchFieldException(
                '''"{expr}" can't be directly attributed to "{field}" as it is a nested field'''
                .format(expr=str(node), field=context["current_field"]))

    def __call__(self, tree):
        context = {"nested_fields": self.nested_fields, "current_field": None}
        return self.visit(tree, context=context)
