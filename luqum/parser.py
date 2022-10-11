# -*- coding: utf-8 -*-
"""The Lucene Query DSL parser based on PLY
"""

# TODO : add reserved chars and escaping, regex
# see : https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-query-string-query.html  # noqa: E501
# https://lucene.apache.org/core/3_6_0/queryparsersyntax.html
import re

import ply.lex as lex
import ply.yacc as yacc

from .exceptions import IllegalCharacterError, ParseSyntaxError
from .head_tail import TokenValue, head_tail, token_headtail
from .tree import (
    AndOperation, Boost, Fuzzy, Group, Not,
    OrOperation, Phrase, Plus, Prohibit, Proximity,
    Range, Regex, SearchField, UnknownOperation, Word,
    create_operation, group_to_fieldgroup,
)


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
# lets catch those expressions apart
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
   [^\s:^~(){{}}[\]/"'+\-\\] # first char is not a space neither some char which have meanings
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
# r'(?P<phrase>"(?:[^\\"]|\\"|\\[^"])*")' # this is quite complicated to handle \"
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
    token_headtail(t, t.value)
    return None  # discard separators


# Warning: PLY is sensible to the order in wich we define terms…

@lex.TOKEN(TERM_RE)
def t_TERM(t):
    # note: it also handles NOT, OR, AND, TO
    # check if it is not a reserved term (an operation)
    t.type = reserved.get(t.value, 'TERM')
    orig_value = t.value
    # it's not, make it a Word
    if t.type == 'TERM':
        m = re.match(TERM_RE, t.value, re.VERBOSE)
        value = m.group("term")
        t.value = Word(value)
    else:
        t.value = TokenValue(t.value)  # gentle wrapper to hande pos, tail, head
    token_headtail(t, orig_value)
    return t


# standard function for simple text tokens
def simple_token(t):
    orig_value = t.value
    t.value = TokenValue(t.value)
    token_headtail(t, orig_value)
    return t


# text of some simple tokens
def t_PLUS(t):
    r'\+'
    return simple_token(t)


def t_MINUS(t):
    r'\-'
    return simple_token(t)


def t_COLUMN(t):
    r':'
    return simple_token(t)


def t_LPAREN(t):
    r'\('
    return simple_token(t)


def t_RPAREN(t):
    r'\)'
    return simple_token(t)


def t_LBRACKET(t):
    r'(\[|\{)'
    return simple_token(t)


def t_RBRACKET(t):
    r'(\]|\})'
    return simple_token(t)


@lex.TOKEN(PHRASE_RE)
def t_PHRASE(t):
    orig_value = t.value
    m = re.match(PHRASE_RE, t.value, re.VERBOSE)
    value = m.group("phrase")
    t.value = Phrase(value)
    token_headtail(t, orig_value)
    return t


@lex.TOKEN(REGEX_RE)
def t_REGEX(t):
    orig_value = t.value
    m = re.match(REGEX_RE, t.value, re.VERBOSE)
    value = m.group("regex")
    t.value = Regex(value)
    token_headtail(t, orig_value)
    return t


@lex.TOKEN(APPROX_RE)
def t_APPROX(t):
    orig_value = t.value
    m = re.match(APPROX_RE, t.value)
    t.value = TokenValue(m.group("degree"))
    token_headtail(t, orig_value)
    return t


@lex.TOKEN(BOOST_RE)
def t_BOOST(t):
    orig_value = t.value
    m = re.match(BOOST_RE, t.value)
    t.value = TokenValue(m.group("force"))
    token_headtail(t, orig_value)
    return t


def t_error(t):
    raise IllegalCharacterError("Illegal character '%s' at position %d" % (t.value, t.lexpos))


lexer = lex.lex()


def p_expression_or(p):
    'expression : expression OR_OP expression'
    p[0] = create_operation(OrOperation, p[1], p[3], op_tail=p[2].tail)
    head_tail.binary_operation(p, op_tail=p[2].tail)


def p_expression_and(p):
    '''expression : expression AND_OP expression'''
    p[0] = create_operation(AndOperation, p[1], p[3], op_tail=p[2].tail)
    head_tail.binary_operation(p, op_tail=p[2].tail)


def p_expression_implicit(p):
    '''expression : expression expression'''
    p[0] = create_operation(UnknownOperation, p[1], p[2], op_tail="")
    head_tail.binary_operation(p, op_tail="")


def p_expression_plus(p):
    '''unary_expression : PLUS unary_expression'''
    p[0] = Plus(p[2])
    head_tail.unary(p)


def p_expression_minus(p):
    '''unary_expression : MINUS unary_expression'''
    p[0] = Prohibit(p[2])
    head_tail.unary(p)


def p_expression_not(p):
    '''unary_expression : NOT unary_expression'''
    p[0] = Not(p[2])
    head_tail.unary(p)


def p_expression_unary(p):
    '''expression : unary_expression'''
    p[0] = p[1]


def p_grouping(p):
    'unary_expression : LPAREN expression RPAREN'
    p[0] = Group(p[2])  # p_field_search will transform to FieldGroup if necessary
    head_tail.paren(p)


def p_range(p):
    '''unary_expression : LBRACKET phrase_or_term TO phrase_or_term RBRACKET'''
    include_low = p[1].value == "["
    include_high = p[5].value == "]"
    p[0] = Range(p[2], p[4], include_low, include_high)
    head_tail.range(p)


def p_field_search(p):
    '''unary_expression : TERM COLUMN unary_expression'''
    if isinstance(p[3], Group):
        p[3] = group_to_fieldgroup(p[3])
    # for field name we take p[1].value for it was captured as a word expression
    p[0] = SearchField(p[1].value, p[3])
    head_tail.search_field(p)


def p_quoting(p):
    'unary_expression : PHRASE'
    p[0] = p[1]


def p_proximity(p):
    '''unary_expression : PHRASE APPROX'''
    p[0] = Proximity(p[1], p[2].value)
    head_tail.post_unary(p)


def p_boosting(p):
    '''expression : expression BOOST'''
    p[0] = Boost(p[1], p[2].value)
    head_tail.post_unary(p)


def p_terms(p):
    '''unary_expression : TERM'''
    p[0] = p[1]


def p_fuzzy(p):
    '''unary_expression : TERM APPROX'''
    p[0] = Fuzzy(p[1], p[2].value)
    head_tail.post_unary(p)


def p_regex(p):
    '''unary_expression : REGEX'''
    p[0] = p[1]


# handling a special case, TO is reserved only in range
def p_to_as_term(p):
    '''unary_expression : TO'''
    p[0] = Word(p[1].value)
    head_tail.simple_term(p)


def p_phrase_or_term(p):
    '''phrase_or_term : TERM
                      | PHRASE'''
    p[0] = p[1]


# Error rule for syntax errors
def p_error(p):
    if p is None:
        error = "unexpected end of expression (maybe due to unmatched parenthesis)"
        pos = "the end"
    else:
        error = "unexpected  '%s'" % p.value
        pos = "position %d" % p.lexpos
    raise ParseSyntaxError("Syntax error in input : %s at %s!" % (error, pos))


parser = yacc.yacc()
"""This is the parser generated by PLY


**Note**: The parser by itself is not thread safe (because PLY is not).
Use :py:func:`luqum.thread.parse` instead
"""
