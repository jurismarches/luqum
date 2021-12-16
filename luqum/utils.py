# -*- coding: utf-8 -*-
"""Various utilities for dealing with syntax trees.

Include base classes to implement a visitor pattern.

"""
# utils pending deprecation
from . import visitor
from .deprecated_utils import (  # noqa: F401
    LuceneTreeTransformer, LuceneTreeVisitor, LuceneTreeVisitorV2)
from .tree import AndOperation, BaseOperation, OrOperation, BoolOperation


class UnknownOperationResolver(visitor.TreeTransformer):
    """Transform the UnknownOperation to OR or AND
    """

    VALID_OPERATIONS = frozenset([None, AndOperation, OrOperation, BoolOperation])
    DEFAULT_OPERATION = AndOperation

    def __init__(self, resolve_to=None, add_head=" "):
        """Initialize a new resolver

        :param resolve_to: must be either None, OrOperation, AndOperation, BoolOperation.

          for the latter three the UnknownOperation is replaced by specified operation.

          if it is None, we use the last operation encountered, as would Lucene do
        """
        if resolve_to not in self.VALID_OPERATIONS:
            raise ValueError("%r is not a valid value for resolve_to" % resolve_to)
        self.resolve_to = resolve_to
        self.add_head = add_head
        super().__init__(track_parents=True)

    def _last_operation(self, context):
        return context.setdefault("last_operation", {})

    def _first_nonop_parent(self, parents):
        for parent in parents:
            if not isinstance(parent, BaseOperation):
                return id(parent)  # use id() because parent might not be hashable
        else:
            return None

    def _track_last_op(self, node, context):
        if self.resolve_to is None:
            # next unknow operation at same level should resolve to my type of operation
            # so track it
            parent = self._first_nonop_parent(context.get("parents", []))
            self._last_operation(context)[parent] = type(node)

    def _get_last_op(self, node, context):
        # search for last operation
        parent = self._first_nonop_parent(context.get("parents", []))
        return self._last_operation(context).get(parent, self.DEFAULT_OPERATION)

    def visit_or_operation(self, node, context):
        self._track_last_op(node, context)
        yield from self.generic_visit(node, context)

    def visit_and_operation(self, node, context):
        self._track_last_op(node, context)
        yield from self.generic_visit(node, context)

    def visit_unknown_operation(self, node, context):
        # resolve
        if self.resolve_to is None:
            operation = self._get_last_op(node, context)
        else:
            operation = self.resolve_to
        new_node = operation(pos=node.pos, size=node.size, head=node.head, tail=node.tail)
        new_node.children = self.clone_children(node, new_node, context)
        # add head to children but the first to separate element from operation (x y --> x AND y)
        for child in new_node.children[1:]:
            child.head = self.add_head + child.head
        yield new_node

    def __call__(self, tree):
        return self.visit(tree)


def normalize_nested_fields_specs(nested_fields):
    """normalize nested_fields specification to only have nested dicts

    :param dict nested_fields:  dict contains fields that are nested in ES
        each nested fields contains either
        a dict of nested fields
        (if some of them are also nested)
        or a list of nesdted fields (this is for commodity)


    ::
        >>> from unittest import TestCase
        >>> TestCase().assertDictEqual(
        ...     normalize_nested_fields_specs(
        ...         {"author" : {"books": ["name", "ref"], "firstname" : None }}),
        ...     {"author" : {"books": {"name": {}, "ref": {}}, "firstname" : {} }})
    """
    if nested_fields is None:
        return {}
    elif isinstance(nested_fields, dict):
        return {k: normalize_nested_fields_specs(v) for k, v in nested_fields.items()}
    else:
        # should be an iterable, transform to dict
        return {sub: {} for sub in nested_fields}


def _flatten_fields_specs(object_fields):
    if not object_fields:
        return [[]]  # parent is a single field
    elif isinstance(object_fields, dict):
        return [
            [k] + v2
            for k, v in object_fields.items()
            for v2 in _flatten_fields_specs(v)]
    else:  # iterable
        return [[k] for k in object_fields]


def flatten_nested_fields_specs(nested_fields):
    """normalize object_fields specification to only have a simple set

    :param dict nested_fields:  contains fields that are object in ES
        has a serie of nested dict.
        List are accepted as well for concisness.

    ::
        >>> from unittest import TestCase
        >>> flatten_nested_fields_specs(None)
        set()
        >>> TestCase().assertEqual(
        ...     flatten_nested_fields_specs(["author.name", "book.title"]),
        ...     set(["author.name", "book.title"]))
        >>> TestCase().assertEqual(
        ...     flatten_nested_fields_specs(
        ...         {"book" : { "author": ["firstname", "lastname"], "title" : None }}),
        ...     set(["book.author.firstname", "book.author.lastname", "book.title"]))
    """
    if isinstance(nested_fields, dict):
        return set(".".join(v) for v in _flatten_fields_specs(nested_fields))
    elif nested_fields is None:
        return set([])
    else:
        return set(nested_fields)


def normalize_object_fields_specs(object_fields):
    """normalize object_fields specification to only have a simple set

    :param dict object_fields:  contains fields that are object in ES
        has a serie of nested dict.
        List are accepted as well for concisness.
        None, which means no spec, is returned as is.

    ::
        >>> from unittest import TestCase
        >>> normalize_object_fields_specs(None) is None
        True
        >>> TestCase().assertEqual(
        ...     normalize_object_fields_specs(["author.name", "book.title"]),
        ...     set(["author.name", "book.title"]))
        >>> TestCase().assertEqual(
        ...     normalize_object_fields_specs(
        ...         {"book" : { "author": ["firstname", "lastname"], "title" : None }}),
        ...     set(["book.author.firstname", "book.author.lastname", "book.title"]))
    """
    if object_fields is None:
        return None
    if isinstance(object_fields, dict):
        return set(".".join(v) for v in _flatten_fields_specs(object_fields))
    else:
        return set(object_fields)
