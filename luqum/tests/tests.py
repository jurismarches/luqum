# -*- coding: utf-8 -*-
from unittest import TestCase

from luqum.exceptions import NestedSearchFieldException

from ..check import LuceneCheck
from ..parser import lexer, parser, ParseError
from ..pretty import Prettifier, prettify
from ..tree import *
from ..utils import (
    LuceneTreeVisitor,
    LuceneTreeTransformer,
    LuceneTreeVisitorV2,
    CheckLuceneTreeVisitor
)


class TestTree(TestCase):

    def test_term_wildcard_true(self):
        self.assertTrue(Term("ba*").has_wildcard())
        self.assertTrue(Term("b*r").has_wildcard())
        self.assertTrue(Term("*ar").has_wildcard())

    def test_term_wildcard_false(self):
        self.assertFalse(Term("bar").has_wildcard())

    def test_term_is_only_a_wildcard(self):
        self.assertTrue(Term('*').is_wildcard())
        self.assertFalse(Term('*o').is_wildcard())
        self.assertFalse(Term('b*').is_wildcard())
        self.assertFalse(Term('b*o').is_wildcard())

    def test_equality_approx(self):
        """
        Regression test for a bug on approx equalities.
        Testing other tokens might be a good idea...
        """
        a1 = Proximity(term='foo', degree=5)
        a2 = Proximity(term='bar', degree=5)
        a3 = Proximity(term='foo', degree=5)

        self.assertNotEqual(a1, a2)
        self.assertEqual(a1, a3)

        f1 = Fuzzy(term='foo', degree=5)
        f2 = Fuzzy(term='bar', degree=5)
        f3 = Fuzzy(term='foo', degree=5)

        self.assertNotEqual(f1, f2)
        self.assertEqual(f1, f3)


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
        self.assertEqual(t.value, "3")
        self.assertEqual(lexer.token().type, "AND_OP")
        self.assertEqual(lexer.token().value, Phrase('"big garage"'))
        t = lexer.token()
        self.assertEqual(t.type, "APPROX")
        self.assertEqual(t.value, "2")
        self.assertEqual(lexer.token().value, Word("dirt"))
        t = lexer.token()
        self.assertEqual(t.type, "APPROX")
        self.assertEqual(t.value, "0.3")
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
                Word("foo"),
                Word("bar")))
        parsed = parser.parse("foo AND bar")
        self.assertEqual(str(parsed), str(tree))
        self.assertEqual(parsed, tree)

    def test_implicit_operations(self):
        tree = (
            UnknownOperation(
                Word("foo"),
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

    def test_minus(self):
        tree = (
            AndOperation(
                AndOperation(
                    Prohibit(
                        Word("test")),
                    Prohibit(
                        Word("foo"))),
                Not(
                    Word("bar"))))
        parsed = parser.parse("-test AND -foo AND NOT bar")
        self.assertEqual(str(parsed), str(tree))
        self.assertEqual(parsed, tree)

    def test_plus(self):
        tree = (
            AndOperation(
                AndOperation(
                    Plus(
                        Word("test")),
                    Word("foo")),
                Plus(
                    Word("bar"))))
        parsed = parser.parse("+test AND foo AND +bar")
        self.assertEqual(str(parsed), str(tree))
        self.assertEqual(parsed, tree)

    def test_phrase(self):
        tree = (
            AndOperation(
                Phrase('"a phrase (AND a complicated~ one)"'),
                Phrase('"Another one"')))
        parsed = parser.parse('"a phrase (AND a complicated~ one)" AND "Another one"')
        self.assertEqual(str(parsed), str(tree))
        self.assertEqual(parsed, tree)

    def test_approx(self):
        tree = (
            UnknownOperation(
                Proximity(
                    Phrase('"foo bar"'),
                    3),
                UnknownOperation(
                    Proximity(
                        Phrase('"foo baz"'),
                        1),
                    UnknownOperation(
                        Fuzzy(
                            Word('baz'),
                            Decimal("0.3")),
                        Fuzzy(
                            Word('fou'),
                            Decimal("0.5"))))))
        parsed = parser.parse('"foo bar"~3 "foo baz"~ baz~0.3 fou~')
        self.assertEqual(str(parsed), str(tree))
        self.assertEqual(parsed, tree)

    def test_boost(self):
        tree = (
            UnknownOperation(
                Boost(
                    Phrase('"foo bar"'),
                    Decimal("3.0")),
                Boost(
                    Group(
                        AndOperation(
                            Word('baz'),
                            Word('bar'))),
                    Decimal("2.1"))))
        parsed = parser.parse('"foo bar"^3 (baz AND bar)^2.1')
        self.assertEqual(str(parsed), str(tree))
        self.assertEqual(parsed, tree)

    def test_groups(self):
        tree = (
           OrOperation(
               Word('test'),
               Group(
                   AndOperation(
                       SearchField(
                           "subject",
                           FieldGroup(
                               OrOperation(
                                   Word('foo'),
                                   Word('bar')))),
                       Word('baz')))))
        parsed = parser.parse('test OR (subject:(foo OR bar) AND baz)')
        self.assertEqual(str(parsed), str(tree))
        self.assertEqual(parsed, tree)

    def test_range(self):
        tree = (
            AndOperation(
                SearchField(
                    "foo",
                    Range(Word("10"), Word("100"), True, True)),
                SearchField(
                    "bar",
                    Range(Word("a*"), Word("*"), True, False))))
        parsed = parser.parse('foo:[10 TO 100] AND bar:[a* TO *}')
        self.assertEqual(str(parsed), str(tree))
        self.assertEqual(parsed, tree)

    def test_flavours(self):
        tree = SearchField(
            "somedate",
            Range(Word("now/d-1d+7H"), Word("now/d+7H"), True, True))
        parsed = parser.parse('somedate:[now/d-1d+7H TO now/d+7H]')
        self.assertEqual(str(parsed), str(tree))
        self.assertEqual(parsed, tree)

    def test_combinations(self):
        # self.assertEqual(parser.parse("subject:test desc:(house OR car)").pval, "")
        tree = (
            UnknownOperation(
                SearchField(
                    "subject",
                    Word("test")),
                AndOperation(
                    SearchField(
                        "desc",
                        FieldGroup(
                            OrOperation(
                                Word("house"),
                                Word("car")))),
                    Not(
                        Proximity(
                            Phrase('"approximatly this"'),
                            3)))))
        parsed = parser.parse('subject:test desc:(house OR car) AND NOT "approximatly this"~3')

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
        tree = SearchField("foo", Range(Word(r"2015-12-19||+2\d"), Word(r"now+3d+12h\h")))
        parsed = parser.parse(r'foo:[2015-12-19||+2\d TO now+3d+12h\h]')
        self.assertEqual(str(tree), str(parsed))
        self.assertEqual(tree, parsed)

    def test_reserved_ko(self):
        """Test reserved word hurt as they hurt lucene
        """
        with self.assertRaises(ParseError):
            parser.parse('foo:NOT')
        with self.assertRaises(ParseError):
            parser.parse('foo:AND')
        with self.assertRaises(ParseError):
            parser.parse('foo:OR')
        with self.assertRaises(ParseError):
            parser.parse('OR')
        with self.assertRaises(ParseError):
            parser.parse('AND')


class TestPrettify(TestCase):

    big_tree = AndOperation(
        Group(OrOperation(Word("baaaaaaaaaar"), Word("baaaaaaaaaaaaaz"))), Word("fooooooooooo"))
    fat_tree = AndOperation(
        SearchField(
            "subject",
            FieldGroup(
                OrOperation(
                    Word("fiiiiiiiiiiz"),
                    AndOperation(Word("baaaaaaaaaar"), Word("baaaaaaaaaaaaaz"))))),
        AndOperation(Word("fooooooooooo"), Word("wiiiiiiiiiz")))

    def test_one_liner(self):
        tree = AndOperation(Group(OrOperation(Word("bar"), Word("baz"))), Word("foo"))
        self.assertEqual(prettify(tree), "( bar OR baz ) AND foo")

    def test_small(self):
        prettify = Prettifier(indent=8, max_len=20)
        self.assertEqual(
            "\n" + prettify(self.big_tree), """
(
        baaaaaaaaaar
        OR
        baaaaaaaaaaaaaz
)
AND
fooooooooooo""")
        self.assertEqual(
            "\n" + prettify(self.fat_tree), """
subject: (
        fiiiiiiiiiiz
        OR
                baaaaaaaaaar
                AND
                baaaaaaaaaaaaaz
)
AND
fooooooooooo
AND
wiiiiiiiiiz""")

    def test_small_inline_ops(self):
        prettify = Prettifier(indent=8, max_len=20, inline_ops=True)
        self.assertEqual("\n" + prettify(self.big_tree), """
(
        baaaaaaaaaar OR
        baaaaaaaaaaaaaz ) AND
fooooooooooo""")
        self.assertEqual("\n" + prettify(self.fat_tree), """
subject: (
        fiiiiiiiiiiz OR
                baaaaaaaaaar AND
                baaaaaaaaaaaaaz ) AND
fooooooooooo AND
wiiiiiiiiiz""")

    def test_normal(self):
        prettify = Prettifier(indent=4, max_len=50)
        self.assertEqual("\n" + prettify(self.big_tree), """
(
    baaaaaaaaaar OR baaaaaaaaaaaaaz
)
AND
fooooooooooo""")
        self.assertEqual("\n" + prettify(self.fat_tree), """
subject: (
    fiiiiiiiiiiz
    OR
        baaaaaaaaaar AND baaaaaaaaaaaaaz
)
AND
fooooooooooo
AND
wiiiiiiiiiz""")

    def test_normal_inline_ops(self):
        prettify = Prettifier(indent=4, max_len=50, inline_ops=True)
        self.assertEqual("\n" + prettify(self.big_tree), """
(
    baaaaaaaaaar OR baaaaaaaaaaaaaz ) AND
fooooooooooo""")
        self.assertEqual("\n" + prettify(self.fat_tree), """
subject: (
    fiiiiiiiiiiz OR
        baaaaaaaaaar AND baaaaaaaaaaaaaz ) AND
fooooooooooo AND
wiiiiiiiiiz""")


class TestCheck(TestCase):

    def test_check_ok(self):
        query = (
            AndOperation(
                SearchField(
                    "f",
                    FieldGroup(
                        AndOperation(
                            Boost(Proximity(Phrase('"foo bar"'), 4), "4.2"),
                            Prohibit(Range("100", "200"))))),
                Group(
                    OrOperation(
                        Fuzzy(Word("baz"), ".8"),
                        Plus(Word("fizz"))))))
        check = LuceneCheck()
        self.assertTrue(check(query))
        self.assertEqual(check.errors(query), [])

    def test_bad_fieldgroup(self):
        check = LuceneCheck()
        query = FieldGroup(Word("foo"))
        self.assertFalse(check(query))
        self.assertEqual(len(check.errors(query)), 1)
        self.assertIn("FieldGroup misuse", check.errors(query)[0])

        query = OrOperation(
            FieldGroup(Word("bar")),
            Word("foo"))
        self.assertFalse(check(query))
        self.assertEqual(len(check.errors(query)), 1)
        self.assertIn("FieldGroup misuse", check.errors(query)[0])

    def test_bad_group(self):
        check = LuceneCheck()
        query = SearchField("f", Group(Word("foo")))
        self.assertFalse(check(query))
        self.assertEqual(len(check.errors(query)), 2)  # one for bad expr, one for misuse
        self.assertIn("Group misuse", "".join(check.errors(query)))

    def test_zealous_or_not(self):
        query = (
            OrOperation(
                Prohibit(Word("foo")),
                Word("bar")))
        check_zealous = LuceneCheck(zeal=1)
        self.assertFalse(check_zealous(query))
        self.assertIn("inconsistent", check_zealous.errors(query)[0])
        check_easy_going = LuceneCheck()
        self.assertTrue(check_easy_going(query))

    def test_bad_field_name(self):
        check = LuceneCheck()
        query = SearchField("foo*", Word("bar"))
        self.assertFalse(check(query))
        self.assertEqual(len(check.errors(query)), 1)
        self.assertIn("not a valid field name", check.errors(query)[0])

    def test_bad_field_expr(self):
        check = LuceneCheck()
        query = SearchField("foo", Prohibit(Word("bar")))
        self.assertFalse(check(query))
        self.assertEqual(len(check.errors(query)), 1)
        self.assertIn("not valid", check.errors(query)[0])

    def test_word_space(self):
        check = LuceneCheck()
        query = Word("foo bar")
        self.assertFalse(check(query))
        self.assertEqual(len(check.errors(query)), 1)
        self.assertIn("space", check.errors(query)[0])

    def test_invalid_characters_in_word_value(self):
        query = Word("foo/bar")
        # Passes if zeal == 0
        check = LuceneCheck()
        self.assertTrue(check(query))
        self.assertEqual(len(check.errors(query)), 0)
        # But not if zeal == 1
        check = LuceneCheck(zeal=1)
        self.assertFalse(check(query))
        self.assertEqual(len(check.errors(query)), 1)
        self.assertIn("Invalid characters", check.errors(query)[0])

    def test_fuzzy_negative_degree(self):
        check = LuceneCheck()
        query = Fuzzy(Word("foo"), "-4.1")
        self.assertFalse(check(query))
        self.assertEqual(len(check.errors(query)), 1)
        self.assertIn("invalid degree", check.errors(query)[0])

    def test_fuzzy_non_word(self):
        check = LuceneCheck()
        query = Fuzzy(Phrase('"foo bar"'), "2")
        self.assertFalse(check(query))
        self.assertEqual(len(check.errors(query)), 1)
        self.assertIn("single term", check.errors(query)[0])

    def test_proximity_non_phrase(self):
        check = LuceneCheck()
        query = Proximity(Word("foo"), "2")
        self.assertFalse(check(query))
        self.assertEqual(len(check.errors(query)), 1)
        self.assertIn("phrase", check.errors(query)[0])

    def test_unknown_item_type(self):
        check = LuceneCheck()
        query = AndOperation("foo", 2)
        self.assertFalse(check(query))
        self.assertEqual(len(check.errors(query)), 2)
        self.assertIn("Unknown item type", check.errors(query)[0])
        self.assertIn("Unknown item type", check.errors(query)[1])


class TreeVisitorTestCase(TestCase):

    class BasicVisitor(LuceneTreeVisitor):
        """ Dummy visitor, simply yielding a list of nodes. """
        def generic_visit(self, node, parents):
            yield node

    class MROVisitor(LuceneTreeVisitor):

        def visit_or_operation(self, node, parents=[]):
            return ["{} OR {}".format(*node.children)]

        def visit_base_operation(self, node, parents=[]):
            return ["{} BASE_OP {}".format(*node.children)]

        def visit_word(self, node, parents=[]):
            return [node.value]

    def test_generic_visit(self):
        tree = (
            AndOperation(
                Word("foo"),
                Word("bar")))

        visitor = LuceneTreeVisitor()
        nodes = list(visitor.visit(tree))
        self.assertEqual(nodes, [])

    def test_basic_traversal(self):
        tree = (
            AndOperation(
                Word("foo"),
                Word("bar")))

        visitor = self.BasicVisitor()
        nodes = list(visitor.visit(tree))

        self.assertListEqual(
            [AndOperation(Word('foo'), Word('bar')), Word('foo'), Word('bar')],
            nodes)

    def test_mro(self):
        visitor = self.MROVisitor()

        tree = OrOperation(Word('a'), Word('b'))
        result = visitor.visit(tree)
        self.assertEquals(list(result), ['a OR b', 'a', 'b'])

        tree = AndOperation(Word('a'), Word('b'))
        result = visitor.visit(tree)
        self.assertEquals(list(result), ['a BASE_OP b', 'a', 'b'])


class TreeTransformerTestCase(TestCase):

    class BasicTransformer(LuceneTreeTransformer):
        """
        Dummy transformer that simply turn any Word node's value into "lol"
        """
        def visit_word(self, node, parent):
            return Word('lol')

    def test_basic_traversal(self):
        tree = (
            AndOperation(
                Word("foo"),
                Word("bar")))

        transformer = self.BasicTransformer()
        new_tree = transformer.visit(tree)

        self.assertEqual(
            (AndOperation(
                Word("lol"),
                Word("lol"))), new_tree)


class TreeVisitorV2TestCase(TestCase):

    class BasicVisitor(LuceneTreeVisitorV2):
        """ Dummy visitor, simply yielding a list of nodes. """
        def generic_visit(self, node, parents):
            yield node
            for c in node.children:
                yield from self.visit(c)

    class MROVisitor(LuceneTreeVisitorV2):

        def visit_or_operation(self, node, parents=[]):
            return "{} OR {}".format(*[self.visit(c) for c in node.children])

        def visit_base_operation(self, node, parents=[]):
            return "{} BASE_OP {}".format(*[self.visit(c) for c in node.children])

        def visit_word(self, node, parents=[]):
            return node.value

    def test_basic_traversal(self):
        tree = (
            AndOperation(
                Word("foo"),
                Word("bar")))

        visitor = self.BasicVisitor()
        nodes = list(visitor.visit(tree))

        self.assertListEqual(
            [AndOperation(Word('foo'), Word('bar')), Word('foo'), Word('bar')],
            nodes)

    def test_mro(self):
        visitor = self.MROVisitor()

        tree = OrOperation(Word('a'), Word('b'))
        result = visitor.visit(tree)
        self.assertEquals(result, 'a OR b')

        tree = OrOperation(AndOperation(Word('a'), Word('b')), Word('c'))
        result = visitor.visit(tree)
        self.assertEquals(result, 'a BASE_OP b OR c')

    def test_generic_visit_fails_by_default(self):
        visitor = self.MROVisitor()
        with self.assertRaises(AttributeError):
            visitor.visit(Phrase('"test"'))


class CheckVisitorTestCase(TestCase):

    def setUp(self):

        NESTED_FIELDS = {
            'author': {
                'book': {
                    'title': '',
                    'format': {
                        'type': ''
                    }
                }
            },
        }

        self.transformer = CheckLuceneTreeVisitor(nested_fields=NESTED_FIELDS)

    def test_correct_nested_lucene_query_wo_point_not_raise(self):
        tree = parser.parse('author:book:title:"foo" AND '
                            'author:book:format:type: "pdf"')
        self.transformer.check(tree)
        self.assertIsNotNone(tree)

    def test_correct_nested_lucene_query_with_point_not_raise(self):
        tree = parser.parse('author.book.title:"foo" AND '
                            'author.book.format.type:"pdf"')
        self.transformer.check(tree)
        self.assertIsNotNone(tree)

    def test_incorrect_nested_lucene_query_wo_point_raise(self):
        tree = parser.parse('author:gender:"Mr" AND '
                            'author:book:format:type:"pdf"')
        with self.assertRaises(NestedSearchFieldException) as e:
            self.transformer.check(tree)
        self.assertIn('"gender"', str(e.exception))

    def test_incorrect_nested_lucene_query_with_point_raise(self):
        tree = parser.parse('author.gender:"Mr" AND '
                            'author.book.format.type:"pdf"')
        with self.assertRaises(NestedSearchFieldException) as e:
            self.transformer.check(tree)
        self.assertIn('"gender"', str(e.exception))

    def test_correct_nested_lucene_query_with_and_wo_point_not_raise(self):
        tree = parser.parse(
            'author:(book.title:"foo" OR book.title:"bar")')
        self.transformer.check(tree)
        self.assertIsNotNone(tree)

    def test_simple_query_with_a_nested_field_should_raise(self):
        tree = parser.parse('author:"foo"')
        with self.assertRaises(NestedSearchFieldException) as e:
            self.transformer.check(tree)
        self.assertIn('"author"', str(e.exception))

    def test_simple_query_with_a_multi_nested_field_should_raise(self):
        tree = parser.parse('author:book:"foo"')
        with self.assertRaises(NestedSearchFieldException) as e:
            self.transformer.check(tree)
        self.assertIn('"book"', str(e.exception))

    def test_complex_query_with_a_multi_nested_field_should_raise(self):
        tree = parser.parse('author:book:"foo" OR author:"Hugo"')
        with self.assertRaises(NestedSearchFieldException):
            self.transformer.check(tree)
