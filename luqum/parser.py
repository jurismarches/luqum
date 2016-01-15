"""The Lucene Query DSL parser
"""

# TODO : add ranges, add boosting, add reserved chars and escaping,
# see : https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-query-string-query.html
# https://lucene.apache.org/core/3_6_0/queryparsersyntax.html
import re

import ply.lex as lex
import ply.yacc as yacc

from .tree import *


reserved = {
  'AND': 'AND_OP',
  'OR': 'OR_OP',
  'NOT': 'MINUS',
}


# tokens of our grammar
tokens = [
    'TERM',
    'PHRASE',
    'APPROX',
    'SEPARATOR',
    'PLUS',
    'COLUMN',
    'LPAREN',
    'RPAREN',
] + list(reserved.values())


# text of some simple tokens
t_PLUS = r'\+'
t_MINUS = r'(-|NOT)'
t_AND_OP = r'AND'
t_OR_OP = r'OR'
t_COLUMN = r':'
t_LPAREN = r'\('
t_RPAREN = r'\)'


# precedence rules
precedence = (
    ('nonassoc', 'TERM'),
    ('left', 'OR_OP',),
    ('left', 'AND_OP'),
    ('right', 'MINUS',),
    ('right', 'PLUS',),
    ('left', 'APPROX'),
    ('nonassoc', 'LPAREN', 'RPAREN'),
    ('nonassoc', 'PHRASE'),
)

# term and phrase
TERM_RE = r'(?P<term>\w+)'
PHRASE_RE = r'(?P<phrase>"[^"]+")'
APPROX_RE = r'~(?P<degree>[0-9.]+)?'


def t_SEPARATOR(t):
    r'\s+'
    pass  # discard separators


@lex.TOKEN(TERM_RE)
def t_TERM(t):
    t.type = reserved.get(t.value, 'TERM')
    if t.type == 'TERM':
        m = re.match(TERM_RE, t.value)
        t.value = Word(m.group("term"))
    return t


@lex.TOKEN(PHRASE_RE)
def t_PHRASE(t):
    m = re.match(PHRASE_RE, t.value)
    t.value = Phrase(m.group("phrase"))
    return t


@lex.TOKEN(APPROX_RE)
def t_APPROX(t):
    m = re.match(APPROX_RE, t.value)
    t.value = m.group("degree")
    return t


# Error handling rule FIXME
def t_error(t):
    print("Illegal character '%s'" % t.value[0])
    t.lexer.skip(1)


lexer = lex.lex()


def p_expression_or(p):
    'expression : expression OR_OP expression'
    p[0] = OrOperation(p[1], p[3])


def p_expression_and(p):
    '''expression : expression AND_OP expression
                           | expression expression'''
    p[0] = AndOperation(p[1], p[len(p) - 1])


def p_expression_plus(p):
    '''unary_expression : PLUS unary_expression'''
    p[0] = Plus(p[2])


def p_expression_minus(p):
    '''unary_expression : MINUS unary_expression'''
    p[0] = Minus(p[2])


def p_expression_unary(p):
    '''expression : unary_expression'''
    p[0] = p[1]


def p_grouping(p):
    'unary_expression : LPAREN expression RPAREN'
    p[0] = Group(p[2])  # Will p_field_search will transform as FieldGroup if necessary


def p_field_search(p):
    'expression : TERM COLUMN unary_expression'
    if isinstance(p[3], Group):
        p[3] = group_to_fieldgroup(p[3])
    p[0] = SearchField(p[1].value, p[3])


def p_quoting(p):
    'unary_expression : PHRASE'
    p[0] = p[1]


def p_proximity(p):
    '''unary_expression : PHRASE APPROX'''
    p[0] = Proximity(p[1], p[2])


def p_terms(p):
    '''unary_expression : TERM'''
    p[0] = p[1]


def p_fuzzy(p):
    '''unary_expression : TERM APPROX'''
    p[0] = Fuzzy(p[1], p[2])


# Error rule for syntax errors FIXME
def p_error(p):
    print("Syntax error in input at %r!" % [p])


parser = yacc.yacc()
