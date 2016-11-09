# -*- coding: utf-8 -*-
"""Various utilities for dealing with syntax trees.

Include base classes to implement a visitor pattern.

"""


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

    def _get_method(self, node):
        for cls in node.__class__.mro():
            try:
                method_name = "{}{}".format(
                    self.visitor_method_prefix,
                    camel_to_lower(cls.__name__)
                )
                return getattr(self, method_name)
            except AttributeError:
                continue
        else:
            return getattr(self, self.generic_visitor_method_name)

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


class LuceneTreeVisitorV2:
    """
    V2 of the LuceneTreeVisitor allowing to evaluate the AST

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

    def _get_method(self, node):
        for cls in node.__class__.mro():
            try:
                method_name = "{}{}".format(
                    self.visitor_method_prefix,
                    camel_to_lower(cls.__name__)
                )
                return getattr(self, method_name)
            except AttributeError:
                continue
        else:
            return getattr(self, self.generic_visitor_method_name)

    def visit(self, node, parents=None):
        """ Basic, recursive traversal of the tree. """
        if parents is None:
            parents = []

        method = self._get_method(node)
        return method(node, parents)

    def generic_visit(self, node, parents=None):
        """
        Default visitor function, called if nothing matches the current node.
        """
        raise AttributeError(
            "No visitor found for this type of node: {}".format(
                node.__class__
            )
        )