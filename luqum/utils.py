# -*- coding: utf-8 -*-
"""Various utilities for dealing with syntax trees.

Include base classes to implement a visitor pattern.

"""
# utils pending deprecation
from . import visitor
from .deprecated_utils import (  # noqa: F401
    LuceneTreeTransformer, LuceneTreeVisitor, LuceneTreeVisitorV2)
from .tree import AndOperation, BaseOperation, OrOperation, BoolOperation, Range, Word


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


class OpenRangeTransformer(visitor.TreeTransformer):
    """Transforms open ranges to normal Range objects, i.e.

    ::

        >=foo            ->   [foo TO *]
        <bar             ->   [* TO bar}

    When *merge_ranges* is set, this also merges open ranges in AND clauses::

        >foo AND <=bar              ->   {foo TO bar]
        [foo TO *] AND [* TO bar]   ->   [foo TO bar]

    The merging of open ranges is performed by collecting all open ranges, and merging any
    open range into any previously collected open range with an open bound. In other words, any
    open bounds are always merged into the first suitable. Additionally, matching is always done
    from left-to-right, so that this holds::

        [a TO *] AND [b TO *] AND [* TO y] AND [* TO z]   ->   [a TO y] AND [b TO z]

    Open ranges in OR and unknown clauses are not adjusted. Use :cls:`UnknownOperationResolver`
    to make sure that unknown operations are resolved first.

    Ranges with none of the bounds set are left unadjusted. Additionally, the ranges must be
    direct siblings of the same parent. Ranges such as ``[foo TO *]^2 AND [* TO bar]^2`` are
    therefore not merged (though ``([foo TO *] AND [* TO bar])^2`` would).
    """

    WILDCARD_WORD = Word("*")

    def __init__(self, merge_ranges=False, add_head=" "):
        self.merge_ranges = merge_ranges
        self.add_head = add_head
        super().__init__(track_parents=True)

    def _get_node_bound_side(self, node):
        """Given a Range node, returns the bound side of the range (either 'high' or 'low').
        This guarantees that the other side is a wildcard. Returns None if the provided node is
        bound on both sides or bound on neither side.

        If the provided node is not a Range object, always returns None.
        """
        if isinstance(node, Range):
            if node.low == self.WILDCARD_WORD and node.high != self.WILDCARD_WORD:
                return 'high'
            elif node.low != self.WILDCARD_WORD and node.high == self.WILDCARD_WORD:
                return 'low'
        return None

    def visit_and_operation(self, node, context):
        if not self.merge_ranges:
            yield from self.generic_visit(node, context)
            return

        new_node = AndOperation(pos=node.pos, size=node.size, head=node.head, tail=node.tail)
        new_node.children = ()

        # We collect all ranges from a AND's children with the same bound side, and pop the
        # first one from the list when we encounter a different bound side. This allows us
        # to join multiple low bounds with multiple high bounds, or vice versa, without
        # requiring them to be in order (see class's docstring for an example)
        #
        # This works correctly because possible_ranges will be a list of open ranges from only one
        # side. Which side this is, is tracked in possible_ranges_bound_side. Any new node of the
        # other side will join into an already existing node, until the list is empty, and we may
        # reset possible_ranges_bound_side again.
        possible_ranges = []

        # possible_ranges_bound_side has no meaning if possible_ranges is empty, and may either
        # be None, or set to a previous value. When adding anything to possible_ranges, we make
        # sure that the direction is correct. All nodes in possible_ranges will be of the same
        # bound side.
        possible_ranges_bound_side = None

        for child in self.clone_children(node, new_node, context):
            # Determines the bound side of the range (high or low), meaning that the other side is
            # a wildcard.
            child_bound_side = self._get_node_bound_side(child)

            if child_bound_side is not None:
                # If we have encountered a Range with only one bound side, we may be able to join it
                if not possible_ranges or possible_ranges_bound_side == child_bound_side:
                    # We have not yet encountered any unbound ranges, or the encountered unbound
                    # ranges are of this node's direction, so store a pointer to this child and we
                    # may be able to join a future range. The flow will continue.
                    possible_ranges.append(child)
                    # Store the direction in the ranges. This assignment only has meaning if
                    # possible_ranges was empty, but the if statement prevents flipping it otherwise
                    possible_ranges_bound_side = child_bound_side
                else:
                    # There is at least one possible range to join to. We adjust the first range
                    # encountered of the different side
                    #
                    # We adjust the first enounter of the range, and do not add the joined one, to
                    # ensure the correct ordering of the different nodes (it is more intuitive to
                    # add it to the first one)
                    joining_child = possible_ranges.pop(0)
                    if child_bound_side == 'low':
                        joining_child.low = child.low
                        joining_child.include_low = child.include_low
                    else:
                        joining_child.high = child.high
                        joining_child.include_high = child.include_high
                    # we should not need to adjust the head/tail because those would be included
                    # from the child range we are joining from

                    # do not add the child we have just merged from
                    continue

            # Could not join the node (either because child_bound_side is None, or it has nothing to
            # join to)
            new_node.children += (child, )

        yield new_node

    def _visit_from_to(self, node, context, bound_side):
        # We omit the child directly for now, as we cannot assign it yet. We add the
        # wildcard element though, and the child is None until we have cloned it.
        if bound_side == 'low':
            args = [None, self.WILDCARD_WORD.clone_item(), node.include, True]
        else:
            args = [self.WILDCARD_WORD.clone_item(), None, True, node.include]

        new_node = Range(
            *args,
            pos=node.pos, size=node.size, head=node.head, tail=node.tail,
        )

        # this forces that we clone the children like we should, but we only expect
        # one return value, so we can simply assign it directly
        child = tuple(self.clone_children(node, new_node, context))[0]
        setattr(new_node, bound_side, child)

        new_node.low.tail += self.add_head
        new_node.high.head += self.add_head
        yield new_node

    def visit_from(self, node, context):
        yield from self._visit_from_to(node, context, 'low')

    def visit_to(self, node, context):
        yield from self._visit_from_to(node, context, 'high')

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
