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

    :param int pos: position of element in orginal text (not accounting for head)
    :param int size: size of element in orginal text (not accounting for head and tail)
    :param str head: non meaningful text before this element
    :param str tail: non meaningful text after this element
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

    #: this attribute permits to list attributes that participate in telling equality of two item
    #: this excludes children (for generic `__eq__` methode will already recursively compare them)
    _equality_attrs = []
    #: this attribute permits to list attributes that defines the children.
    #: Order is important.
    _children_attrs = []

    def __init__(self, pos=None, size=None, head="", tail=""):
        self.pos = pos
        self.size = size
        self.head = head
        self.tail = tail

    def clone_item(self, **kwargs):
        """clone an item, but not its children !

        This is particularly useful for the :py:class:`.visitor.TreeTransformer` pattern.

        :param dict kwargs: those item will be added to `__init__` call.
            It's a simple way to change some values of target item.
        """
        return self._clone_item(cls=type(self), **kwargs)

    def _clone_item(self, cls, *args, **kwargs):
        """internal implementation of clone_item (for specific sub classes tweaks)

        :param type cls: the new class
        """
        attrs = {"pos": self.pos, "size": self.size, "head": self.head, "tail": self.tail}
        # we can _equality_attrs as they normally correspond to what we need to copy
        attrs.update((attr_name, getattr(self, attr_name)) for attr_name in self._equality_attrs)
        # use NoneItem for children using _children_attrs
        attrs.update((attr_name, NONE_ITEM) for attr_name in self._children_attrs)
        # add optional kwargs
        attrs.update(**kwargs)
        return cls(*args, **attrs)

    @property
    def children(self):
        """As base of a tree structure, an item may have children"""
        return [getattr(self, attr) for attr in self._children_attrs]

    @children.setter
    def children(self, value):
        """generic setter for children.

        Having a setter for children in useful for generic manipulations
        like in :py:mod:`luqum.visitor`
        """
        if len(value) != len(self._children_attrs):
            num_children = len(value) if value else "no"
            raise ValueError(
                f"{type(self)} accepts {num_children} children,"
                f" and you try to set {len(value)} children"
            )
        for attr, v in zip(self._children_attrs, value):
            setattr(self, attr, v)

    def _head_tail(self, value, head_tail):
        if head_tail:
            return self.head + value + self.tail
        else:
            return value

    def span(self, head_tail=False):
        """return (start, end) position of this element in global expression.

        :param bool head_tail: should span include head and tail of element ?
        """
        if self.pos is None:
            start, end = None, None
        else:
            start = self.pos - (len(self.head) if head_tail else 0)
            end = self.pos + self.size + (len(self.tail) if head_tail else 0)
        return start, end

    def __repr__(self):
        children = ", ".join(c.__repr__() for c in self.children)
        return "%s(%s)" % (self.__class__.__name__, children)

    def __eq__(self, other):
        """a generic equal operation

        It make uses of :py:attr:`Item._equality_attrs`,
        and also recursively compare children
        """
        return (
            self is other  # shortcut
        ) or (
            self.__class__ == other.__class__ and
            len(self.children) == len(other.children) and
            all(getattr(self, a, _MARKER) == getattr(other, a, _MARKER)
                for a in self._equality_attrs) and
            all(c.__eq__(d) for c, d in zip(self.children, other.children))
        )


class NoneItem(Item):
    """This Item is a place holder, think to it as None.

    It can be used, eg. to initialize an element childrens, until we feed in the real children.
    """

    def __str__(self, head_tail=False):
        return ""


#: an instanciation of NoneItem, as it is always the same
NONE_ITEM = NoneItem()


class SearchField(Item):
    """Indicate wich field the search expression operates on

    eg: *desc* in ``desc:(this OR that)``

    :param str name: name of the field
    :param expr: the searched expression
    """
    _equality_attrs = ['name']
    _children_attrs = ["expr"]

    def __init__(self, name, expr, **kwargs):
        self.name = name
        self.expr = expr
        super().__init__(**kwargs)

    def __str__(self, head_tail=False):
        value = self.name + ":" + self.expr.__str__(head_tail=True)
        return self._head_tail(value, head_tail)

    def __repr__(self):
        return "SearchField(%r, %s)" % (self.name, self.expr.__repr__())


class BaseGroup(Item):
    """Base class for group of expressions or field values

    :param expr: the expression inside parenthesis
    """
    _children_attrs = ["expr"]

    def __init__(self, expr, **kwargs):
        self.expr = expr
        super().__init__(**kwargs)

    def __str__(self, head_tail=False):
        value = "(%s)" % self.expr.__str__(head_tail=True)
        return self._head_tail(value, head_tail)


class Group(BaseGroup):
    """Group sub expressions
    """


class FieldGroup(BaseGroup):
    """Group values for a query on a field
    """


def group_to_fieldgroup(g):
    return FieldGroup(g.expr, pos=g.pos, size=g.size, head=g.head, tail=g.tail)


class Range(Item):
    """A Range

    :param low: lower bound
    :param high: higher bound
    :param bool include_low: wether lower bound is included
    :param bool include_high: wether higher bound is included
    """

    LOW_CHAR = {True: '[', False: '{'}
    HIGH_CHAR = {True: ']', False: '}'}

    _equality_attrs = ['include_high', 'include_low']
    _children_attrs = ["low", "high"]

    def __init__(self, low, high, include_low=True, include_high=True, **kwargs):
        self.low = low
        self.high = high
        self.include_low = include_low
        self.include_high = include_high
        super().__init__(**kwargs)

    def __str__(self, head_tail=False):
        value = "%s%sTO%s%s" % (
            self.LOW_CHAR[self.include_low],
            self.low.__str__(head_tail=True),
            self.high.__str__(head_tail=True),
            self.HIGH_CHAR[self.include_high])
        return self._head_tail(value, head_tail)


class Term(Item):
    """Base for terms

    :param str value: the value
    """
    WILDCARDS_PATTERN = re.compile(r"((?<=[^\\])[?*]|\\\\[?*]|^[?*])")  # non escaped * and ?
    # see
    # https://lucene.apache.org/core/3_6_0/queryparsersyntax.html#Escaping%20Special%20Characters
    WORD_ESCAPED_CHARS = re.compile(r'\\([+\-&|!(){}[\]^"~*?:\\])')

    _equality_attrs = ['value']

    def __init__(self, value, **kwargs):
        self.value = value
        super().__init__(**kwargs)

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

    def __str__(self, head_tail=False):
        value = self.value
        return self._head_tail(value, head_tail)

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
    def __init__(self, value, **kwargs):
        super(Phrase, self).__init__(value, **kwargs)
        assert self.value.endswith('"') and self.value.startswith('"'), (
               "Phrase value must contain the quotes")


class Regex(Term):
    """A regex term, that is a sequence of words enclose in slashes

    :param str value: the value, including the slashes. Eg. ``'/my regex/'``
    """
    def __init__(self, value, **kwargs):
        super(Regex, self).__init__(value, **kwargs)
        assert value.endswith('/') and value.startswith('/'), (
               "Regex value must contain the slashes")


class BaseApprox(Item):
    """Base for approximations, that is fuzziness and proximity
    """
    _equality_attrs = ['degree']
    _children_attrs = ["term"]

    def __init__(self, term, degree=None, **kwargs):
        self.term = term
        self._implicit_degree = degree is None  # this is just for display
        self.degree = self._normalize_degree(degree)
        super().__init__(**kwargs)

    def __repr__(self):
        return "%s(%s, %s)" % (self.__class__.__name__, self.term.__repr__(), self.degree)

    def __str__(self, head_tail=False):
        value = "%s~%s" % (
            self.term.__str__(head_tail=True),
            self.degree if not self._implicit_degree else "",
        )
        return self._head_tail(value, head_tail)


class Fuzzy(BaseApprox):
    """Fuzzy search on word

    :param Word term: the approximated term
    :param degree: the degree which will be converted to :py:class:`decimal.Decimal`.
    """
    def _normalize_degree(self, degree):
        if degree is None:
            degree = 0.5
        if not isinstance(degree, Decimal):
            degree = Decimal(degree).normalize()
        return degree


class Proximity(BaseApprox):
    """Proximity search on phrase

    :param Phrase term: the approximated phrase
    :param degree: the degree which will be converted to :py:func:`int`.
    """

    def _normalize_degree(self, degree):
        if degree is None:
            degree = 1
        return int(degree)


class Boost(Item):
    """A term for boosting a value or a group there of

    :param expr: the boosted expression
    :param force: boosting force, will be converted to :py:class:`decimal.Decimal`
    """
    _equality_attrs = ['force']
    _children_attrs = ["expr"]

    def __init__(self, expr, force, **kwargs):
        self.expr = expr
        self.force = Decimal(force).normalize() if force is not None else 1
        self.implicit_force = force is None
        super().__init__(**kwargs)

    def __repr__(self):
        return "%s(%s, %s)" % (self.__class__.__name__, self.expr.__repr__(), self.force)

    def __str__(self, head_tail=False):
        force = "" if self.implicit_force else self.force
        value = "%s^%s" % (self.expr.__str__(head_tail=True), force)
        return self._head_tail(value, head_tail)


class BaseOperation(Item):
    """
    Parent class for binary operations are binary operation used to join expressions,
    like OR and AND

    :param operands: expressions to apply operation on
    """

    def __init__(self, *operands, **kwargs):
        self.operands = operands
        super().__init__(**kwargs)

    def __str__(self, head_tail=False):
        value = ("%s" % self.op).join(o.__str__(head_tail=True) for o in self.operands)
        return self._head_tail(value, head_tail)

    @property
    def children(self):
        """children are left and right expressions
        """
        return self.operands

    @children.setter
    def children(self, value):
        """Generic setter for children

        :param iterable value: operands
        """
        self.operands = tuple(value)


class BoolOperation(BaseOperation):
    """Lucene Boolean Query.

    This operation assumes that the query builder can utilize a boolean operator
    with three possible sections, must, should and must_not. If the
    UnknownOperationResolver is asked to resolve_to this operation, the query
    builder can utilize this operator directly instead of nested AND/OR.
    This also makes it possible to correctly support Lucene queries such as:
    "apples +bananas -vegetables".

    .. seealso::
        the :py:class:`.utils.UnknownOperationResolver`
    """
    op = ""


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


class OrOperation(BaseOperation):
    """OR expression
    """
    op = 'OR'


class AndOperation(BaseOperation):
    """AND expression
    """
    op = 'AND'


def create_operation(cls, a, b, op_tail=" "):
    """Create operation between a and b, merging if a or b is already an operation of same class

    :param a: left operand
    :param b: right operand
    :param op_tail: tail of operation token
    """
    operands = []
    operands.extend(a.operands if isinstance(a, cls) else [a])
    left_operands = b.operands if isinstance(b, cls) else [b]
    left_operands[0].head += op_tail
    operands.extend(left_operands)
    return cls(*operands)


class Unary(Item):
    """Parent class for unary operations

    :param a: the expression the operator applies on
    """
    _children_attrs = ["a"]

    def __init__(self, a, **kwargs):
        self.a = a
        super().__init__(**kwargs)

    def __str__(self, head_tail=False):
        value = "%s%s" % (self.op, self.a.__str__(head_tail=True))
        return self._head_tail(value, head_tail)


class Plus(Unary):
    """plus, unary operation
    """
    op = "+"


class Not(Unary):
    op = 'NOT'


class Prohibit(Unary):
    """The negation
    """
    op = "-"
