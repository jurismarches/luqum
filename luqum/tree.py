"""Elements that will constitute the parse tree of a query
"""


class Item:
    """Base class for all items that compose the parse tree.

    An item is a part of a request.
    """

    @property
    def children(self):
        """As base of a tree structure, an item may have children"""
        # empty by default
        return []

    def split_op(self):
        """Split the request part on operations
        """
        for c in self.children:
            yield from c.split_op()

    def __eq__(self, other):
        """a basic equal operation
        """
        return (self.__class__ == other.__class__ and self.__dict__ == other.__dict__)


class SearchField(Item):
    """Indicate wich field the search expression operates on

    eg: *desc* in *desc:(this OR that)
    """
    def __init__(self, name, expr):
        self.name = name
        self.expr = expr

    def __str__(self):
        return str(self.name) + ":" + str(self.expr)

    @property
    def children(self):
        yield self.expr


class BaseGroup(Item):
    """Base class for group of expressions or field values
    """
    def __init__(self, expr):
        self.expr = expr

    def __str__(self):
        return "(%s)" % str(self.expr)

    @property
    def children(self):
        yield self.expr

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, str(self))


class Group(BaseGroup):
    """Group sub expressions
    """


class FieldGroup(BaseGroup):
    """Group values for a query on a field
    """


def group_to_fieldgroup(g):
    return FieldGroup(g.expr)


class Term(Item):
    """Base for terms
    """

    def __init__(self, value):
        self.value = value

    def __str__(self):
        return self.value

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, str(self))


class Word(Term):
    pass


class Phrase(Term):
    """A phrase term, that is a sequence of words enclose in quotes
    """
    pass


class BaseApprox(Item):
    """Base for approximations
    """

class Fuzzy(BaseApprox):
    """Fuzzy search on word
    """
    def __init__(self, term, degree=None):
        self.term = term
        if degree is None:
            degree = 0.5
        self.degree = float(degree)

    def __str__(self):
        return "%s~%f" % (self.term, self.degree)


class Proximity(BaseApprox):
    """Proximity search on phrase
    """
    def __init__(self, term, degree=None):
        self.term = term
        if degree is None:
            degree = 1
        self.degree = int(degree)

    def __str__(self):
        return "%s~" % self.term + ("%d" % self.degree if self.degree is not None else "")


class Operation(Item):
    """Parent class for binary operations are binary operation used to join expressions,
    like OR and AND
    """
    def __init__(self, a, b):
        self.a = a
        self.b = b

    def __str__(self):
        return "%s %s %s" % (self.a, self.op, self.b)

    @property
    def children(self):
        yield self.a
        yield self.b

    def split_op(self):
        return self.op
        yield self.a
        yield self.b


class OrOperation(Operation):
    op = 'OR'


class AndOperation(Operation):
    op = 'AND'


class Unary(Item):
    """Parent class for unary operations
    """

    def __init__(self, a):
        self.a = a

    def __str__(self):
        return "%s%s" % (self.op, self.a)

    @property
    def children(self):
        yield self.a


class Plus(Unary):
    """plus operation
    """
    op = "+"


class Minus(Unary):
    """The negation
    """
    op = "-"
