# -*- coding: utf-8 -*-
"""This module provides a pretty printer for lucene query tree.
"""
from .tree import BaseOperation, BaseGroup, SearchField


class _StickMarker:
    """Use in list between two elements that must stick together
    """

    def __len__(self):
        return 0


# a marker to avoid a new line between two elements
_STICK_MARKER = _StickMarker()


class Prettifier(object):
    """Class to generate a pretty printer.
    """

    def __init__(self, indent=4, max_len=80, inline_ops=False):
        """
        The pretty printer factory.

        :param int indent: number of space for indentation
        :param int max_len: maximum line length in number of characters.
            Prettyfier will do its best to keep inside those margin,
            but as it can only split on operators, it may not be possible.
        :param bool inline_ops: if False (default) operators are printed on a new line
          if True, operators are printed at the end of the line.
        """
        self.indent = indent
        self.prefix = " " * self.indent
        self.max_len = max_len
        self.inline_ops = inline_ops

    def _get_chains(self, element, parent=None):
        """return a list of string and list, and recursively

        An inner list represent a level of indentation
        A string is information from the level
        """
        if isinstance(element, BaseOperation):
            if not isinstance(parent, BaseOperation) or element.op == parent.op:
                # same level, this is just associativity
                num_children = len(element.children)
                for n, child in enumerate(element.children):
                    yield from self._get_chains(child, element)
                    if n < num_children - 1:
                        if self.inline_ops:
                            yield _STICK_MARKER
                        if element.op:
                            yield element.op
            else:
                # another operation, raise level
                new_level = []
                num_children = len(element.children)
                for n, child in enumerate(element.children):
                    new_level.extend(self._get_chains(child, element))
                    if n < num_children - 1:
                        if self.inline_ops:
                            new_level.append(_STICK_MARKER)
                        if element.op:
                            new_level.append(element.op)
                yield new_level
        elif isinstance(element, BaseGroup):
            # raise level
            yield "("
            yield list(self._get_chains(element.expr, element))
            if self.inline_ops:
                yield _STICK_MARKER
            yield ")"
        elif isinstance(element, SearchField):
            # use recursion on sub expression
            yield element.name + ":"
            yield _STICK_MARKER
            yield from self._get_chains(element.expr, element)
        else:
            # simple element
            yield str(element)

    def _count_chars(self, element):
        """Replace each element by the element and a count of chars in it (and recursively)

        This will help, compute if elements can stand on a line or not
        """
        if isinstance(element, list):
            with_counts = [self._count_chars(c)for c in element]
            # when counting we add a space for joining
            return with_counts, sum(n + 1 for c, n in with_counts) - 1
        else:
            return element, len(element)

    def _apply_stick(self, elements):
        last = None
        sticking = False
        for current in elements:
            if current == _STICK_MARKER:
                assert last is not None, "_STICK_MARKER should never be first !"
                sticking = True
            elif sticking:
                last += " " + current
                sticking = False
            else:
                if last is not None:
                    yield last
                last = current
        yield last

    def _concatenates(self, chain_with_counts, char_counts, level=0, in_one_liner=False):
        """taking the result of _get_chains after passing through _count_chars,
        arrange things, using newlines and indentation when necessary

        :return string: prettified expression
        """
        # evaluate if it's feasible in one-line
        one_liner = in_one_liner or char_counts < self.max_len - (self.indent * level)
        new_level = level if one_liner else level + 1
        elements = [
            self._concatenates(c, n, level=new_level, in_one_liner=one_liner)
            if isinstance(c, list)
            else c
            for c, n in chain_with_counts]
        elements = self._apply_stick(elements)
        prefix = self.prefix if level and not in_one_liner else ""
        join_char = " " if one_liner else ("\n" + prefix)
        return prefix + join_char.join(line for c in elements for line in c.split("\n"))

    def __call__(self, tree):
        """Pretty print the query represented by tree

        :param tree: a query tree using elements from :py:mod:`luqum.tree`
        """
        chains = list(self._get_chains(tree))
        chain_with_counts, total = self._count_chars(chains)
        return self._concatenates(chain_with_counts, total)


prettify = Prettifier()
"""prettify function with default parameters
"""
