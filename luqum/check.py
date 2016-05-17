# -*- coding: utf-8 -*-
import functools
import math
import re

from . import tree


def camel_to_lower(name):
    return "".join(
        "_" + w.lower() if w.isupper() else w.lower()
        for w in name).lstrip("_")


sign = functools.partial(math.copysign, 1)


def _check_children(f):
    """A decorator to call check on item children
    """
    @functools.wraps(f)
    def wrapper(self, item, parents):
        yield from f(self, item, parents)
        for child in item.children:
            yield from self.check(child, parents + [item])
    return wrapper


class LuceneCheck:
    """Check if a query is consistent

    This is intended to use with query constructed as tree,
    as well as those parsed by the parser, which is more tolerant.

    :param int zeal: if zeal > 0 do extra check of some pitfalls, depending on zeal level
    """
    field_name_re = re.compile(r"^\w+$")
    space_re = re.compile(r"\s")
    invalid_term_chars_re = re.compile(r"[+/-]")

    SIMPLE_EXPR_FIELDS = (
        tree.Boost, tree.Proximity, tree.Fuzzy, tree.Word, tree.Phrase)

    FIELD_EXPR_FIELDS = tuple(list(SIMPLE_EXPR_FIELDS) + [tree.FieldGroup])

    def __init__(self, zeal=0):
        self.zeal = zeal

    def _check_field_name(self, fname):
        return self.field_name_re.match(fname) is not None

    @_check_children
    def check_search_field(self, item, parents):
        if not self._check_field_name(item.name):
            yield "%s is not a valid field name" % item.name
        if not isinstance(item.expr, self.FIELD_EXPR_FIELDS):
            yield "field expression is not valid : %s" % item

    @_check_children
    def check_group(self, item, parents):
        if parents and isinstance(parents[-1], tree.SearchField):
            yield "Group misuse, after SearchField you should use Group : %s" % parents[-1]

    @_check_children
    def check_field_group(self, item, parents):
        if not parents or not isinstance(parents[-1], tree.SearchField):
            yield ("FieldGroup misuse, it must be used after SearchField : %s" %
                   (parents[-1] if parents else item))

    def check_range(self, item, parents):
        # TODO check lower bound <= higher bound taking into account wildcard and numbers
        return iter([])

    def check_word(self, item, parents):
        if self.space_re.search(item.value):
            yield "A single term value can't hold a space %s" % item
        if self.zeal and self.invalid_term_chars_re.search(item.value):
            yield "Invalid characters in term value: %s" % item.value

    def check_fuzzy(self, item, parents):
        if sign(item.degree) < 0:
            yield "invalid degree %d, it must be positive" % item.degree
        if not isinstance(item.term, tree.Word):
            yield "Fuzzy should be on a single term in %s" % str(item)

    def check_proximity(self, item, parents):
        if not isinstance(item.term, tree.Phrase):
            yield "Proximity can be only on a phrase in %s" % str(item)

    @_check_children
    def check_boost(self, item, parents):
        return iter([])

    @_check_children
    def check_or_operation(self, item, parents):
        return iter([])

    @_check_children
    def check_and_operation(self, item, parents):
        return iter([])

    @_check_children
    def check_plus(self, item, parents):
        return iter([])

    def _check_not_operator(self, item, parents):
        """Common checker for NOT and - operators"""
        if self.zeal:
            if isinstance(parents[-1], tree.OrOperation):
                yield ("Prohibit or Not really means 'AND NOT' " +
                       "wich is inconsistent with OR operation in %s" % parents[-1])

    @_check_children
    def check_not(self, item, parents):
        return self._check_not_operator(item, parents)

    @_check_children
    def check_prohibit(self, item, parents):
        return self._check_not_operator(item, parents)

    def check(self, item, parents=[]):
        # dispatching check to anothe method
        for cls in item.__class__.mro():
            meth = getattr(self, "check_" + camel_to_lower(cls.__name__), None)
            if meth is not None:
                yield from meth(item, parents)
                break
        else:
            yield "Unknown item type %s : %s" % (item.__class__.__name__, str(item))

    def __call__(self, tree):
        """return True only if there are no error
        """
        for error in self.check(tree):
            return False
        return True

    def errors(self, tree):
        """List all errors"""
        return list(self.check(tree))
