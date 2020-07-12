# -*- coding: utf-8 -*-
"""Elements that will constitute the parse tree of a query.

You may use these items to build a tree representing a query,
or get a tree as the result of parsing a query string.
"""
import re
from decimal import Decimal

_MARKER = object()


class Item(object):
    """Base class for all items that compose the parse tree.

    An item is a part of a request.
    """

    # /!\ Note on Item (and subclasses) __magic__ methods: /!\
    #
    # Since we're dealing with recursive structures, we must avoid using
    # the builtin helper methods when dealing with nested objects in
    # __magic__ methods.
    #
    # As the helper usually calls the relevant method, we end up with two
    # function calls instead of one, and end up hitting python's max recursion
    # limit twice as fast!
    #
    # This is why we're calling c.__repr__ instead of repr(c) in the __repr__
    # method. Same thing applies for all magic methods (__str__, __eq__, and any
    # other we might add in the future).

    _equality_attrs = []

    @property
    def children(self):
        """As base of a tree structure, an item may have children"""
        # empty by default
        return []

    def __repr__(self):
        children = ", ".join(c.__repr__() for c in self.children)
        return "%s(%s)" % (self.__class__.__name__, children)

    def __eq__(self, other):
        """a basic equal operation
        """
        return (self.__class__ == other.__class__ and
                len(self.children) == len(other.children) and
                all(getattr(self, a, _MARKER) == getattr(other, a, _MARKER)
                    for a in self._equality_attrs) and
                all(c.__eq__(d) for c, d in zip(self.children, other.children)))


class SearchField(Item):
    """Indicate wich field the search expression operates on

    eg: *desc* in ``desc:(this OR that)``

    :param str name: name of the field
    :param expr: the searched expression
    """
    _equality_attrs = ['name']

    def __init__(self, name, expr):
        self.name = name
        self.expr = expr

    def __str__(self):
        return self.name + ":" + self.expr.__str__()

    def __repr__(self):
        return "SearchField(%r, %s)" % (self.name, self.expr.__repr__())

    @property
    def children(self):
        """the only child is the expression"""
        return [self.expr]


class BaseGroup(Item):
    """Base class for group of expressions or field values

    :param expr: the expression inside parenthesis
    """
    def __init__(self, expr):
        self.expr = expr

    def __str__(self):
        return "(%s)" % self.expr.__str__()

    @property
    def children(self):
        """the only child is the expression"""
        return [self.expr]


class Group(BaseGroup):
    """Group sub expressions
    """


class FieldGroup(BaseGroup):
    """Group values for a query on a field
    """


def group_to_fieldgroup(g):  # FIXME: no use !
    return FieldGroup(g.expr)


class Range(Item):
    """A Range

    :param low: lower bound
    :param high: higher bound
    :param bool include_low: wether lower bound is included
    :param bool include_high: wether higher bound is included
    """

    LOW_CHAR = {True: '[', False: '{'}
    HIGH_CHAR = {True: ']', False: '}'}

    def __init__(self, low, high, include_low=True, include_high=True):
        self.low = low
        self.high = high
        self.include_low = include_low
        self.include_high = include_high

    @property
    def children(self):
        """children are lower and higher bound expressions"""
        return [self.low, self.high]

    def __str__(self):
        return "%s%s TO %s%s" % (
            self.LOW_CHAR[self.include_low],
            self.low.__str__(),
            self.high.__str__(),
            self.HIGH_CHAR[self.include_high])


class Term(Item):
    """Base for terms

    :param str value: the value
    """
    WILDCARDS_PATTERN = re.compile(r"((?<=[^\\])[?*]|^[?*])")  # non escaped * and ?
    # see
    # https://lucene.apache.org/core/3_6_0/queryparsersyntax.html#Escaping%20Special%20Characters
    WORD_ESCAPED_CHARS = re.compile(r'\\([+\-&|!(){}[\]^"~*?:\\])')

    _equality_attrs = ['value']

    def __init__(self, value):
        self.value = value

    @property
    def unescaped_value(self):
        # remove '\' that escape characters
        return self.WORD_ESCAPED_CHARS.sub(r'\1', self.value)

    def is_wildcard(self):
        """:return bool: True if value is the wildcard ``*``
        """
        return self.value == "*"

    def iter_wildcards(self):
        """list wildcards contained in value and their positions
        """
        for matched in self.WILDCARDS_PATTERN.finditer(self.value):
            yield matched.span(), matched.group()

    def split_wildcards(self):
        """split term on wildcards
        """
        return self.WILDCARDS_PATTERN.split(self.value)

    def has_wildcard(self):
        """:return bool: True if value contains a wildcards
        """
        return any(self.iter_wildcards())

    def __str__(self):
        return self.value

    def __repr__(self):
        return "%s(%r)" % (self.__class__.__name__, str(self))


class Word(Term):
    """A single word term

    :param str value: the value
    """


class Phrase(Term):
    """A phrase term, that is a sequence of words enclose in quotes

    :param str value: the value, including the quotes. Eg. ``'"my phrase"'``
    """
    def __init__(self, value):
        super(Phrase, self).__init__(value)
        assert self.value.endswith('"') and self.value.startswith('"'), (
               "Phrase value must contain the quotes")


class Regex(Term):
    """A regex term, that is a sequence of words enclose in slashes

    :param str value: the value, including the slashes. Eg. ``'/my regex/'``
    """
    def __init__(self, value):
        super(Regex, self).__init__(value)
        assert value.endswith('/') and value.startswith('/'), (
               "Regex value must contain the slashes")


class BaseApprox(Item):
    """Base for approximations, that is fuzziness and proximity
    """
    _equality_attrs = ['term', 'degree']

    def __repr__(self):  # pragma: no cover
        return "%s(%s, %s)" % (self.__class__.__name__, self.term.__repr__(), self.degree)

    @property
    def children(self):
        return [self.term]


class Fuzzy(BaseApprox):
    """Fuzzy search on word

    :param Word term: the approximated term
    :param degree: the degree which will be converted to :py:class:`decimal.Decimal`.
    """
    def __init__(self, term, degree=None):
        self.term = term
        if degree is None:
            degree = 0.5
        self.degree = Decimal(degree).normalize()

    def __str__(self):
        return "%s~%s" % (self.term, self.degree)


class Proximity(BaseApprox):
    """Proximity search on phrase

    :param Phrase term: the approximated phrase
    :param degree: the degree which will be converted to :py:func:`int`.
    """
    def __init__(self, term, degree=None):
        self.term = term
        if degree is None:
            degree = 1
        self.degree = int(degree)

    def __str__(self):
        return "%s~" % self.term + ("%d" % self.degree if self.degree is not None else "")


class Boost(Item):
    """A term for boosting a value or a group there of

    :param expr: the boosted expression
    :param force: boosting force, will be converted to :py:class:`decimal.Decimal`
    """
    def __init__(self, expr, force):
        self.expr = expr
        self.force = Decimal(force).normalize()

    @property
    def children(self):
        """The only child is the boosted expression
        """
        return [self.expr]

    def __str__(self):
        return "%s^%s" % (self.expr.__str__(), self.force)


class BaseOperation(Item):
    """
    Parent class for binary operations are binary operation used to join expressions,
    like OR and AND

    :param operands: expressions to apply operation on
    """
    def __init__(self, *operands):
        self.operands = operands

    def __str__(self):
        return (" %s " % self.op).join(str(o) for o in self.operands)

    @property
    def children(self):
        """children are left and right expressions
        """
        return self.operands


class UnknownOperation(BaseOperation):
    """Unknown Boolean operator.

    .. warning::
        This is used to represent implicit operations (ie: term:foo term:bar),
        as we cannot know for sure which operator should be used.

        Lucene seem to use whatever operator was used before reaching that one,
        defaulting to AND, but we cannot know anything about this at parsing
        time...
    .. seealso::
        the :py:class:`.utils.UnknownOperationResolver` to resolve those nodes to OR and AND
    """
    op = ''

    def __str__(self):
        return " ".join(str(o) for o in self.operands)


class OrOperation(BaseOperation):
    """OR expression
    """
    op = 'OR'


class AndOperation(BaseOperation):
    """AND expression
    """
    op = 'AND'


def create_operation(cls, a, b):
    """Create operation between a and b, merging if a or b is already an operation of same class
    """
    operands = []
    operands.extend(a.operands if isinstance(a, cls) else [a])
    operands.extend(b.operands if isinstance(b, cls) else [b])
    return cls(*operands)


class Unary(Item):
    """Parent class for unary operations

    :param a: the expression the operator applies on
    """

    def __init__(self, a):
        self.a = a

    def __str__(self):
        return "%s%s" % (self.op, self.a.__str__())

    @property
    def children(self):
        return [self.a]


class Plus(Unary):
    """plus, unary operation
    """
    op = "+"


class Not(Unary):
    op = 'NOT '


class Prohibit(Unary):
    """The negation
    """
    op = "-"
