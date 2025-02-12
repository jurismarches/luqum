from decimal import Decimal
from unittest import TestCase

import ply.lex as lex
import pytest

from luqum.exceptions import IllegalCharacterError, ParseSyntaxError
from luqum.parser import lexer, parser, parse
from luqum.tree import (
    SearchField, FieldGroup, Group,
    Word, Phrase, Regex, Proximity, Fuzzy, Boost, Range, From, To,
    Not, AndOperation, OrOperation, Plus, Prohibit, UnknownOperation)
from tests import alternative_lexer


class TestLexer(TestCase):
    """Test lexer
    """
    def test_basic(self):

        lexer.input(
            'subject:test desc:(house OR car)^3 AND "big garage"~2 dirt~0.3 OR foo:{a TO z*]')
        self.assertEqual(lexer.token().value, Word("subject"))
        self.assertEqual(lexer.token().type, "COLUMN")
        self.assertEqual(lexer.token().value, Word("test"))
        self.assertEqual(lexer.token().value, Word("desc"))
        self.assertEqual(lexer.token().type, "COLUMN")
        self.assertEqual(lexer.token().type, "LPAREN")
        self.assertEqual(lexer.token().value, Word("house"))
        self.assertEqual(lexer.token().type, "OR_OP")
        self.assertEqual(lexer.token().value, Word("car"))
        self.assertEqual(lexer.token().type, "RPAREN")
        t = lexer.token()
        self.assertEqual(t.type, "BOOST")
        self.assertEqual(t.value.value, "3")
        self.assertEqual(lexer.token().type, "AND_OP")
        self.assertEqual(lexer.token().value, Phrase('"big garage"'))
        t = lexer.token()
        self.assertEqual(t.type, "APPROX")
        self.assertEqual(t.value.value, "2")
        self.assertEqual(lexer.token().value, Word("dirt"))
        t = lexer.token()
        self.assertEqual(t.type, "APPROX")
        self.assertEqual(t.value.value, "0.3")
        self.assertEqual(lexer.token().type, "OR_OP")
        self.assertEqual(lexer.token().value, Word("foo"))
        self.assertEqual(lexer.token().type, "COLUMN")
        self.assertEqual(lexer.token().type, "LBRACKET")
        self.assertEqual(lexer.token().value, Word("a"))
        self.assertEqual(lexer.token().type, "TO")
        self.assertEqual(lexer.token().value, Word("z*"))
        self.assertEqual(lexer.token().type, "RBRACKET")
        self.assertEqual(lexer.token(), None)

    def test_accept_flavours(self):
        lexer.input('somedate:[now/d-1d+7H TO now/d+7H]')

        self.assertEqual(lexer.token().value, Word('somedate'))

        self.assertEqual(lexer.token().type, "COLUMN")
        self.assertEqual(lexer.token().type, "LBRACKET")

        self.assertEqual(lexer.token().value, Word("now/d-1d+7H"))
        self.assertEqual(lexer.token().type, "TO")
        self.assertEqual(lexer.token().value, Word("now/d+7H"))

        self.assertEqual(lexer.token().type, "RBRACKET")


class TestParser(TestCase):
    """Test base parser

    .. note:: we compare str(tree) before comparing tree, because it's more easy to debug
    """

    def test_simplest(self):
        tree = (
            AndOperation(
                Word("foo", tail=" "),
                Word("bar", head=" ")))
        parsed = parser.parse("foo AND bar")
        self.assertEqual(str(parsed), str(tree))
        self.assertEqual(parsed, tree)

    def test_implicit_operations(self):
        tree = (
            UnknownOperation(
                Word("foo", tail=" "),
                Word("bar")))
        parsed = parser.parse("foo bar")
        self.assertEqual(str(parsed), str(tree))
        self.assertEqual(parsed, tree)

    def test_simple_field(self):
        tree = (
            SearchField(
                "subject",
                Word("test")))
        parsed = parser.parse("subject:test")
        self.assertEqual(str(parsed), str(tree))
        self.assertEqual(parsed, tree)

    def test_escaping_word(self):
        query = r'test\+\-\&\&\|\|\!\(\)\{\}\[\]\^\"\~\*\?\:\\test'
        tree = Word(query)
        unescaped = r'test+-&&||!(){}[]^"~*?:\test'
        parsed = parser.parse(query)
        self.assertEqual(str(parsed), query)
        self.assertEqual(parsed, tree)
        self.assertEqual(parsed.unescaped_value, unescaped)

    def test_escaping_word_first_letter(self):
        for letter in r'+-&|!(){}[]^"~*?:\\<>':
            with self.subTest("letter %s" % letter):
                query = r"\%stest" % letter
                tree = Word(query)
                unescaped = "%stest" % letter
                parsed = parser.parse(query)
                self.assertEqual(str(parsed), query)
                self.assertEqual(parsed, tree)
                self.assertEqual(parsed.unescaped_value, unescaped)

    def test_escaping_word_unbounded_equals(self):
        """This tests that <\\=foo correctly translates to <(=foo)"""
        query = r"<\=test"
        tree = To(Word("\\=test"), False)
        parsed = parser.parse(query)
        self.assertEqual(str(parsed), query)
        self.assertEqual(parsed, tree)
        self.assertEqual(parsed.a.unescaped_value, "=test")

    def test_escaping_phrase(self):
        query = r'"test \"ph\rase"'
        tree = Phrase(query)
        unescaped = '"test "phrase"'
        parsed = parser.parse(query)
        self.assertEqual(str(parsed), query)
        self.assertEqual(parsed, tree)
        self.assertEqual(parsed.unescaped_value, unescaped)

    def test_escaping_column(self):
        # non regression for issue #30
        query = r'ip:1000\:\:1000\:\:1/24'
        tree = SearchField('ip', Word(r'1000\:\:1000\:\:1/24'))
        parsed = parser.parse(query)
        self.assertEqual(parsed, tree)
        self.assertEqual(str(parsed), query)
        self.assertEqual(parsed.children[0].unescaped_value, "1000::1000::1/24")

    def test_escaping_single_column(self):
        # non regression for issue #30
        query = r'1000\:1000\:\:1/24'
        tree = Word(r'1000\:1000\:\:1/24')
        parsed = parser.parse(query)
        self.assertEqual(parsed, tree)
        self.assertEqual(str(parsed), query)
        self.assertEqual(parsed.unescaped_value, "1000:1000::1/24")

    def test_boost_default_to_one(self):
        query = "boost^ me^1"
        parsed = parser.parse(query)
        tree = UnknownOperation(Boost(Word("boost"), None), Boost(Word("me"), 1))
        self.assertEqual(parsed, tree)
        self.assertEqual(parsed.operands[0].force, 1)
        self.assertEqual(parsed.operands[0].implicit_force, True)
        self.assertEqual(parsed.operands[1].force, 1)
        self.assertEqual(parsed.operands[1].implicit_force, False)
        self.assertEqual(str(parsed), query)

    def test_field_with_number(self):
        # non regression for issue #10
        tree = (
            SearchField(
                "field_42",
                Word("42")))
        parsed = parser.parse("field_42:42")
        self.assertEqual(str(parsed), str(tree))
        self.assertEqual(parsed, tree)

    def test_comma_can_be_a_term(self):
        # non regression for issue #79
        tree = UnknownOperation(Word("hi", tail=" "), Word(",", tail=" "), Word("bye"))
        parsed = parser.parse("hi , bye")
        self.assertEqual(str(parsed), str(tree))
        self.assertEqual(parsed, tree)

    def test_minus(self):
        tree = (
            AndOperation(
                Prohibit(
                    Word("test", tail=" ")),
                Prohibit(
                    Word("foo", tail=" "), head=" "),
                Not(
                    Word("bar", head=" "), head=" ")))
        parsed = parser.parse("-test AND -foo AND NOT bar")
        self.assertEqual(str(parsed), str(tree))
        self.assertEqual(parsed, tree)

    def test_plus(self):
        tree = (
            AndOperation(
                Plus(
                    Word("test", tail=" ")),
                Word("foo", head=" ", tail=" "),
                Plus(
                    Word("bar"), head=" ")))
        parsed = parser.parse("+test AND foo AND +bar")
        self.assertEqual(str(parsed), str(tree))
        self.assertEqual(parsed, tree)

    def test_phrase(self):
        tree = (
            AndOperation(
                Phrase('"a phrase (AND a complicated~ one)"', tail=" "),
                Phrase('"Another one"', head=" ")))
        parsed = parser.parse('"a phrase (AND a complicated~ one)" AND "Another one"')
        self.assertEqual(str(parsed), str(tree))
        self.assertEqual(parsed, tree)

    def test_regex(self):
        tree = (
            AndOperation(
                Regex('/a regex (with some.*match+ing)?/', tail=" "),
                Regex('/Another one/', head=" ")))
        parsed = parser.parse('/a regex (with some.*match+ing)?/ AND /Another one/')
        self.assertEqual(str(parsed), str(tree))
        self.assertEqual(parsed, tree)

    def test_approx(self):
        tree = (
            UnknownOperation(
                Proximity(
                    Phrase('"foo bar"'),
                    3,
                    tail=" "),
                Proximity(
                    Phrase('"foo baz"'),
                    None,
                    tail=" "),
                Fuzzy(
                    Word('baz'),
                    Decimal("0.3"),
                    tail=" "),
                Fuzzy(
                    Word('fou'),
                    None)))
        parsed = parser.parse('"foo bar"~3 "foo baz"~ baz~0.3 fou~')
        self.assertEqual(str(parsed), str(tree))
        self.assertEqual(parsed, tree)

    def test_boost(self):
        tree = (
            UnknownOperation(
                Boost(
                    Phrase('"foo bar"'),
                    Decimal("3.0"),
                    tail=" "),
                Boost(
                    Group(
                        AndOperation(
                            Word('baz', tail=" "),
                            Word('bar', head=" "))),
                    Decimal("2.1"))))
        parsed = parser.parse('"foo bar"^3 (baz AND bar)^2.1')
        self.assertEqual(str(parsed), str(tree))
        self.assertEqual(parsed, tree)

    def test_groups(self):
        tree = (
           OrOperation(
               Word('test', tail=" "),
               Group(
                   AndOperation(
                       SearchField(
                           "subject",
                           FieldGroup(
                               OrOperation(
                                   Word('foo', tail=" "),
                                   Word('bar', head=" "))),
                           tail=" "),
                       Word('baz', head=" ")),
                   head=" ")))
        parsed = parser.parse('test OR (subject:(foo OR bar) AND baz)')
        self.assertEqual(str(parsed), str(tree))
        self.assertEqual(parsed, tree)

    def test_range(self):
        tree = (
            AndOperation(
                SearchField(
                    "foo",
                    Range(Word("10", tail=" "), Word("100", head=" "), True, True),
                    tail=" "),
                SearchField(
                    "bar",
                    Range(Word("a*", tail=" "), Word("*", head=" "), True, False),
                    head=" ")))
        parsed = parser.parse('foo:[10 TO 100] AND bar:[a* TO *}')
        self.assertEqual(str(parsed), str(tree))
        self.assertEqual(parsed, tree)

    def test_flavours(self):
        tree = SearchField(
            "somedate",
            Range(Word("now/d-1d+7H", tail=" "), Word("now/d+7H", head=" "), True, True))
        parsed = parser.parse('somedate:[now/d-1d+7H TO now/d+7H]')
        self.assertEqual(str(parsed), str(tree))
        self.assertEqual(parsed, tree)

    def test_combinations(self):
        # self.assertEqual(parser.parse("subject:test desc:(house OR car)").pval, "")
        tree = (
            UnknownOperation(
                SearchField(
                    "subject",
                    Word("test"),
                    tail=" "),
                AndOperation(
                    SearchField(
                        "desc",
                        FieldGroup(
                            OrOperation(
                                Word("house", tail=" "),
                                Word("car", head=" "))),
                        tail=" "),
                    Not(
                        Proximity(
                            Phrase('"approximatly this"'),
                            3,
                            head=" "),
                        head=" "))))
        parsed = parser.parse('subject:test desc:(house OR car) AND NOT "approximatly this"~3')

        self.assertEqual(str(parsed), str(tree))
        self.assertEqual(parsed, tree)

    def test_from_to(self):
        """Tests that all unbounded ranges work correctly"""
        tree = (
            AndOperation(
                SearchField("foo", From(Word("10"), False), tail=" "),
                SearchField("bar", To(Word("11"), True), tail=" ", head=" "),
                SearchField("baz", From(Word("100"), True), tail=" ", head=" "),
                SearchField("fou", To(Phrase('"200"'), False), head=" ")
            )
        )
        parsed = parser.parse('foo:>10 AND bar:<=11 AND baz:>=100 AND fou:<"200"')
        self.assertEqual(str(parsed), str(tree))
        self.assertEqual(parsed, tree)

    def test_from_to_fieldgroup(self):
        """Additional test for the use of combined open ranges (could have been a normal range)"""
        tree = (
            SearchField("foo", FieldGroup(UnknownOperation(
                From(Word("10"), True, tail=" "),
                To(Word("11"), False)
            )))
        )
        parsed = parser.parse('foo:(>=10 <11)')
        self.assertEqual(str(parsed), str(tree))
        self.assertEqual(parsed, tree)

    def test_from_boost_plus_precedence(self):
        """Tests that boost, plus and from have correct precedence"""
        tree = Plus(Boost(From(Word("10"), True), 3))
        parsed = parser.parse('+>=10^3')
        self.assertEqual(str(parsed), str(tree))
        self.assertEqual(parsed, tree)

    def test_precedence(self):
        """We test that unary + and - associate with the closest (unary) expression, and do not
        become associated with the entire ``2 AND 3`` expression

        Also, Boost must be closer than Plus: ``+1 AND +2^1`` must be ``+1 AND +(2^1)``
        """
        tree = (
            OrOperation(
                Word("1", tail=" "),
                AndOperation(
                    Plus(Boost(Fuzzy(Word("2"), 1), 1), tail=" "),
                    Word("3", head=" "),
                    head=" ",
                ),
            )
        )
        parsed = parser.parse('1 OR +2~1^1 AND 3')

        self.assertEqual(str(parsed), str(tree))
        self.assertEqual(parsed, tree)

    def test_precedence_unknown(self):
        """Tests whether the implied unknown operation has the lowest associativity.
        This is independent of whether UnknownOperation resolves to AND or OR, as per
        evidence from Apache's Lucene parsing.

        Default operator: AND, parsed as: +1 +(+2 +3) +4
        Default operator: OR, parsed as:  1 (+2 +3) 4

        """
        tree = (
            UnknownOperation(
                Word("1", tail=" "),
                AndOperation(
                    Word("2", tail=" "),
                    Word("3", head=" "),
                    tail=" ",
                ),
                Word("4"),
            )
        )
        parsed = parser.parse('1 2 AND 3 4')

        self.assertEqual(str(parsed), str(tree))
        self.assertEqual(parsed, tree)

    def test_reserved_ok(self):
        """Test reserved word do not hurt in certain positions
        """
        tree = SearchField("foo", Word("TO"))
        parsed = parser.parse('foo:TO')
        self.assertEqual(str(tree), str(parsed))
        self.assertEqual(tree, parsed)
        tree = SearchField("foo", Word("TO*"))
        parsed = parser.parse('foo:TO*')
        self.assertEqual(str(tree), str(parsed))
        self.assertEqual(tree, parsed)
        tree = SearchField("foo", Word("NOT*"))
        parsed = parser.parse('foo:NOT*')
        self.assertEqual(str(tree), str(parsed))
        self.assertEqual(tree, parsed)
        tree = SearchField("foo", Phrase('"TO AND OR"'))
        parsed = parser.parse('foo:"TO AND OR"')
        self.assertEqual(str(tree), str(parsed))
        self.assertEqual(tree, parsed)

    def test_date_in_field(self):
        tree = SearchField("foo", Word("2015-12-19"))
        parsed = parser.parse('foo:2015-12-19')
        self.assertEqual(str(tree), str(parsed))
        self.assertEqual(tree, parsed)
        tree = SearchField("foo", Word("2015-12-19T22:30"))
        parsed = parser.parse('foo:2015-12-19T22:30')
        self.assertEqual(str(tree), str(parsed))
        self.assertEqual(tree, parsed)
        tree = SearchField("foo", Word("2015-12-19T22:30:45"))
        parsed = parser.parse('foo:2015-12-19T22:30:45')
        self.assertEqual(str(tree), str(parsed))
        self.assertEqual(tree, parsed)
        tree = SearchField("foo", Word("2015-12-19T22:30:45.234Z"))
        parsed = parser.parse('foo:2015-12-19T22:30:45.234Z')
        self.assertEqual(str(tree), str(parsed))
        self.assertEqual(tree, parsed)

    def test_datemath_in_field(self):
        tree = SearchField("foo", Word(r"2015-12-19||+2\d"))
        parsed = parser.parse(r'foo:2015-12-19||+2\d')
        self.assertEqual(str(tree), str(parsed))
        self.assertEqual(tree, parsed)
        tree = SearchField("foo", Word(r"now+2h+20m\h"))
        parsed = parser.parse(r'foo:now+2h+20m\h')
        self.assertEqual(str(tree), str(parsed))
        self.assertEqual(tree, parsed)

    def test_date_in_range(self):
        # juste one funky expression
        tree = SearchField(
            "foo",
            Range(Word(r"2015-12-19||+2\d", tail=" "), Word(r"now+3d+12h\h", head=" ")))
        parsed = parser.parse(r'foo:[2015-12-19||+2\d TO now+3d+12h\h]')
        self.assertEqual(str(tree), str(parsed))
        self.assertEqual(tree, parsed)

    def test_reserved_ko(self):
        """Test reserved word hurt as they hurt lucene
        """
        with self.assertRaises(ParseSyntaxError) as raised:
            parser.parse('foo:NOT')
        self.assertTrue(
            str(raised.exception).startswith("Syntax error in input : unexpected end of expr"))
        with self.assertRaises(ParseSyntaxError) as raised:
            parser.parse('foo:AND')
        self.assertEqual(
            str(raised.exception),
            "Syntax error in input : unexpected  'AND' at position 4!",
        )
        with self.assertRaises(ParseSyntaxError) as raised:
            parser.parse('foo:OR')
        self.assertEqual(
            str(raised.exception),
            "Syntax error in input : unexpected  'OR' at position 4!",
        )
        with self.assertRaises(ParseSyntaxError) as raised:
            parser.parse('OR')
        self.assertEqual(
            str(raised.exception),
            "Syntax error in input : unexpected  'OR' at position 0!",
        )
        with self.assertRaises(ParseSyntaxError) as raised:
            parser.parse('AND')
        self.assertEqual(
            str(raised.exception),
            "Syntax error in input : unexpected  'AND' at position 0!",
        )

    def test_parse_error_on_unmatched_parenthesis(self):
        with self.assertRaises(ParseSyntaxError) as raised:
            parser.parse('((foo bar) ')
        self.assertTrue(
            str(raised.exception).startswith("Syntax error in input : unexpected end of expr"))

    def test_parse_error_on_unmatched_bracket(self):
        with self.assertRaises(ParseSyntaxError) as raised:
            parser.parse('[foo TO bar')
        self.assertTrue(
            str(raised.exception).startswith("Syntax error in input : unexpected end of expr"))

    def test_parse_error_on_range(self):
        with self.assertRaises(ParseSyntaxError) as raised:
            parser.parse('[foo TO ]')
        self.assertEqual(
            str(raised.exception),
            "Syntax error in input : unexpected  ']' at position 8!",
        )

    def test_illegal_character_exception(self):
        with self.assertRaises(IllegalCharacterError) as raised:
            parser.parse('\\')
        self.assertEqual(
            str(raised.exception),
            "Illegal character '\\' at position 0",
        )

    def test_negative_values_in_ranges(self):
        parsed = parser.parse("[-1 TO 5]")
        self.assertEqual(str(parsed), "[-1 TO 5]")

        parsed = parser.parse("[-10 TO -1]")
        self.assertEqual(str(parsed), "[-10 TO -1]")

        # semantically incorrect but correct from the parser's perspective
        parsed = parser.parse("[5 TO -1]")
        self.assertEqual(str(parsed), "[5 TO -1]")


def test_lex_global_state():
    """
    Last Lexer is used globally by default by the parser. If another library
    creates another lexer, it should not impact luqum.

    More info: [Multiple Parsers and
    Lexers](http://www.dabeaz.com/ply/ply.html#ply_nn37)
    """
    qs = '(title:"foo bar" AND body:"quick fox")'

    lex.lex(module=alternative_lexer)

    with pytest.raises(ParseSyntaxError):
        parser.parse(qs, lexer=lex.lexer)

    # if there is a "luqum.exceptions.ParseSyntaxError",
    # the wrong lexer was used.
    parse(qs)
    parser.parse(qs)
