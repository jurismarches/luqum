# -*- coding: utf-8 -*-
"""Various utilities for dealing with syntax trees.

Include base classes to implement a visitor pattern.

"""

from .tree import BaseOperation, SearchField, Unary
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


class CheckLuceneTreeVisitor(LuceneTreeVisitorV2):
    """
    Visit the lucene tree to make some checks
    """

    def __init__(self, *args, **kwargs):
        nested_fields = kwargs.get('nested_fields')
        self.nested_fields = nested_fields if nested_fields else {}
        self.__complete_path = []  # edited through self._add_path

        assert(isinstance(self.nested_fields, dict))

    @property
    def _complete_path(self):
        return self.__complete_path

    def _add_path(self, path, children_name=None):
        """
        Clean complete path before add it
        """
        self.__complete_path = self._clean_complete_path()
        if children_name:
            for sub_path_list in self._complete_path:
                if sub_path_list[-1] in children_name:
                    sub_path_list.append(path)
        else:
            self.__complete_path[-1].append(path)

    def _clean_complete_path(self):
        """
        Make list of paths unique
        """
        cleaned_list = []
        for sublist in self._complete_path:
            if sublist not in cleaned_list:
                cleaned_list.append(sublist)
        return cleaned_list

    def _is_correct_path(self, path_list, subdict):
        """
        Verify if a path is in correct order in dict else raise
        """
        current_path = path_list.pop()
        if current_path in subdict:
            if not path_list:  # all path have been consumed
                return True
            else:
                return self._is_correct_path(
                    path_list,
                    subdict[current_path]
                )
        else:
            raise NestedSearchFieldException(current_path)

    def check(self, *args, **kwargs):
        """
        Call the visit method and then verify all nested path are in the
        defined nested fields
        """
        self.visit(*args, **kwargs)
        for sub in self._complete_path:
            if len(sub) > 1:
                self._is_correct_path(sub, self.nested_fields)

    def generic_visit(self, node, parent):
        """
        If nothing matches the current node, visit children
        """
        for child in node.children:
            self.visit(child, node)

    def _get_all_children_node_name(self, node):
        children_name = []
        for child in node.children:
            local_children_name = self._get_all_children_node_name(child)
            if local_children_name:
                children_name.extend(local_children_name)
            if isinstance(child, SearchField):
                for name in child.name.split('.'):
                    children_name.append(name)

        return list(set(children_name))

    def visit_search_field(self, node, parent):
        """
        On search field node, create list to keep current path in it
        """
        if not parent or isinstance(parent, (BaseOperation, Unary)):
            self.__complete_path.append([])
        self.visit(node.children[0], node)
        if '.' in node.name:
            for n in reversed(node.name.split('.')):
                self._add_path(n)
        else:
            children_name = None
            if node.children:
                children_name = self._get_all_children_node_name(node)
            self._add_path(node.name, children_name=children_name)
