# -*- coding: utf-8 -*-
"""The Lucene Query DSL parser based on PLY
"""

# TODO : add reserved chars and escaping, regex
# see : https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-query-string-query.html
# https://lucene.apache.org/core/3_6_0/queryparsersyntax.html
import re

import ply.lex as lex
import ply.yacc as yacc

from .tree import *


class ParseError(ValueError):
    """Exception while parsing a lucene statement
    """
    pass


reserved = {
  'AND': 'AND_OP',
  'OR': 'OR_OP',
  'NOT': 'NOT',
  'TO': 'TO'}


# tokens of our grammar
tokens = (
    ['TERM',
     'PHRASE',
     'REGEX',
     'APPROX',
     'BOOST',
     'MINUS',
     'PLUS',
     'COLUMN',
     'LPAREN',
     'RPAREN',
     'LBRACKET',
     'RBRACKET'] +
    # we sort to have a deterministic order, so that gammar signature does not changes
    sorted(list(reserved.values())))


# text of some simple tokens
t_PLUS = r'\+'
t_MINUS = r'\-'
t_NOT = 'NOT'
t_AND_OP = r'AND'
t_OR_OP = r'OR'
t_COLUMN = r':'
t_LPAREN = r'\('
t_RPAREN = r'\)'
t_LBRACKET = r'(\[|\{)'
t_RBRACKET = r'(\]|\})'


# precedence rules
precedence = (
    ('left', 'OR_OP',),
    ('left', 'AND_OP'),
    ('nonassoc', 'MINUS',),
    ('nonassoc', 'PLUS',),
    ('nonassoc', 'APPROX'),
    ('nonassoc', 'BOOST'),
    ('nonassoc', 'LPAREN', 'RPAREN'),
    ('nonassoc', 'LBRACKET', 'TO', 'RBRACKET'),
    ('nonassoc', 'REGEX'),
    ('nonassoc', 'PHRASE'),
    ('nonassoc', 'TERM'),
)

# term

# the case of : which is used in date is problematic because it is also a delimiter
# lets catch those expressions appart
# Note : we must use positive look behind, because regexp engine is eager,
# and it's only arrived at ':' that it will try this rule
TIME_RE = r'''
(?<=T\d{2}):  # look behind for T and two digits: hours
\d{2}         # minutes
(:\d{2})?     # seconds
'''
# this is a wide catching expression, to also include date math.
# Inspired by the original lucene parser:
# https://github.com/apache/lucene-solr/blob/master/lucene/queryparser/src/java/org/apache/lucene/queryparser/surround/parser/QueryParser.jj#L189
# We do allow the wildcards operators ('*' and '?') as our parser doesn't deal with them.

TERM_RE = r'''
(?P<term>  # group term
  (?:
   [^\s:^~(){{}}[\]/,"'+\-\\] # first char is not a space neither some char which have meanings
                              # note: escape of "-" and "]"
                              #       and doubling of "{{}}" (because we use format)
   |                          # but
   \\.                        # we can start with an escaped character
  )
  ([^\s:^\\~(){{}}[\]]        # following chars
   |                          # OR
   \\.                        # an escaped char
   |                          # OR
   {time_re}                  # a time expression
  )*
)
'''.format(time_re=TIME_RE)
# phrase
PHRASE_RE = r'''
(?P<phrase>  # phrase
  "          # opening quote
  (?:        # repeating
    [^\\"]   # - a char which is not escape or end of phrase
    |        # OR
    \\.      # - an escaped char
  )*
  "          # closing quote
)'''
#r'(?P<phrase>"(?:[^\\"]|\\"|\\[^"])*")' # this is quite complicated to handle \"
# modifiers after term or phrase
APPROX_RE = r'~(?P<degree>[0-9.]+)?'
BOOST_RE = r'\^(?P<force>[0-9.]+)?'

# regex
REGEX_RE = r'''
(?P<regex>  # regex
  /         # open slash
  (?:       # repeating
    [^\\/]  # - a char which is not escape or end of regex
    |       # OR
    \\.     # an escaped char
  )*
  /         # closing slash
)'''

def t_SEPARATOR(t):
    r'\s+'
    pass  # discard separators

@lex.TOKEN(TERM_RE)
def t_TERM(t):
    # check if it is not a reserved term (an operation)
    t.type = reserved.get(t.value, 'TERM')
    # it's not, make it a Word
    if t.type == 'TERM':
        m = re.match(TERM_RE, t.value, re.VERBOSE)
        value = m.group("term")
        t.value = Word(value)
    return t


@lex.TOKEN(PHRASE_RE)
def t_PHRASE(t):
    m = re.match(PHRASE_RE, t.value, re.VERBOSE)
    value = m.group("phrase")
    t.value = Phrase(value)
    return t

@lex.TOKEN(REGEX_RE)
def t_REGEX(t):
    m = re.match(REGEX_RE, t.value, re.VERBOSE)
    value = m.group("regex")
    t.value = Regex(value)
    return t


@lex.TOKEN(APPROX_RE)
def t_APPROX(t):
    m = re.match(APPROX_RE, t.value)
    t.value = m.group("degree")
    return t


@lex.TOKEN(BOOST_RE)
def t_BOOST(t):
    m = re.match(BOOST_RE, t.value)
    t.value = m.group("force")
    return t


# Error handling rule FIXME
def t_error(t):  # pragma: no cover
    print("Illegal character '%s'" % t.value[0])
    t.lexer.skip(1)


lexer = lex.lex()


def p_expression_or(p):
    'expression : expression OR_OP expression'
    p[0] = create_operation(OrOperation, p[1], p[3])


def p_expression_and(p):
    '''expression : expression AND_OP expression'''
    p[0] = create_operation(AndOperation, p[1], p[len(p) - 1])


def p_expression_implicit(p):
    '''expression : expression expression'''
    p[0] = create_operation(UnknownOperation, p[1], p[2])


def p_expression_plus(p):
    '''unary_expression : PLUS unary_expression'''
    p[0] = Plus(p[2])


def p_expression_minus(p):
    '''unary_expression : MINUS unary_expression'''
    p[0] = Prohibit(p[2])


def p_expression_not(p):
    '''unary_expression : NOT unary_expression'''
    p[0] = Not(p[2])


def p_expression_unary(p):
    '''expression : unary_expression'''
    p[0] = p[1]


def p_grouping(p):
    'unary_expression : LPAREN expression RPAREN'
    p[0] = Group(p[2])  # Will p_field_search will transform as FieldGroup if necessary


def p_range(p):
    '''unary_expression : LBRACKET phrase_or_term TO phrase_or_term RBRACKET'''
    include_low = p[1] == "["
    include_high = p[5] == "]"
    p[0] = Range(p[2], p[4], include_low, include_high)


def p_field_search(p):
    '''unary_expression : TERM COLUMN unary_expression'''
    if isinstance(p[3], Group):
        p[3] = group_to_fieldgroup(p[3])
    # for field name we take p[1].value for it was captured as a word expression
    p[0] = SearchField(p[1].value, p[3])


def p_quoting(p):
    'unary_expression : PHRASE'
    p[0] = p[1]


def p_proximity(p):
    '''unary_expression : PHRASE APPROX'''
    p[0] = Proximity(p[1], p[2])


def p_boosting(p):
    '''expression : expression BOOST'''
    p[0] = Boost(p[1], p[2])


def p_terms(p):
    '''unary_expression : TERM'''
    p[0] = p[1]


def p_fuzzy(p):
    '''unary_expression : TERM APPROX'''
    p[0] = Fuzzy(p[1], p[2])

def p_regex(p):
    '''unary_expression : REGEX'''
    p[0] = p[1]

# handling a special case, TO is reserved only in range
def p_to_as_term(p):
    '''unary_expression : TO'''
    p[0] = Word(p[1])


def p_phrase_or_term(p):
    '''phrase_or_term : TERM
                      | PHRASE'''
    p[0] = p[1]


# Error rule for syntax errors
# TODO : should report better
def p_error(p):
    if p is None:
        p = "(probably at end of input, may be unmatch parenthesis or so)"
    raise ParseError("Syntax error in input at %r!" % p)


parser = yacc.yacc()
"""This is the parser generated by PLY
"""
