# -*- coding: utf-8 -*-
"""
.. todo:: split this file in multiple file: tree, lexer, parser
"""
from decimal import Decimal
from unittest import TestCase

from luqum.exceptions import NestedSearchFieldException, ObjectSearchFieldException

from ..check import LuceneCheck, CheckNestedFields
from ..parser import lexer, parser, ParseError
from ..pretty import Prettifier, prettify
from ..tree import (
    SearchField, FieldGroup, Group, Item,
    Term, Word, Phrase, Regex, Proximity, Fuzzy, Boost, Range,
    NONE_ITEM, Not, AndOperation, OrOperation, Plus, Prohibit, UnknownOperation)
from ..utils import UnknownOperationResolver


class TestTree(TestCase):

    def test_term_wildcard_true(self):
        self.assertTrue(Term("ba*").has_wildcard())
        self.assertTrue(Term("b*r").has_wildcard())
        self.assertTrue(Term("*ar").has_wildcard())
        self.assertTrue(Term("ba?").has_wildcard())
        self.assertTrue(Term("b?r").has_wildcard())
        self.assertTrue(Term("?ar").has_wildcard())
        self.assertTrue(Term("?a*").has_wildcard())
        self.assertTrue(Term(r"\?a*").has_wildcard())
        self.assertTrue(Term(r"?a\*").has_wildcard())
        self.assertTrue(Term("*").has_wildcard())
        self.assertTrue(Term("?").has_wildcard())

    def test_term_wildcard_false(self):
        self.assertFalse(Term("bar").has_wildcard())
        self.assertFalse(Term(r"bar\*").has_wildcard())
        self.assertFalse(Term(r"b\?r\*").has_wildcard())

    def test_term_is_only_a_wildcard(self):
        self.assertTrue(Term('*').is_wildcard())
        self.assertFalse(Term('*o').is_wildcard())
        self.assertFalse(Term('b*').is_wildcard())
        self.assertFalse(Term('b*o').is_wildcard())
        self.assertFalse(Term('?').is_wildcard())

    def test_term_iter_wildcard(self):
        self.assertListEqual(
            list(Term(r"a?b\*or*and\?").iter_wildcards()),
            [((1, 2), "?"), ((7, 8), "*")],
            )
        self.assertListEqual(
            list(Term(r"\**\**").iter_wildcards()),
            [((2, 3), "*"), ((5, 6), "*")],
            )

    def test_term_split_wildcard(self):
        self.assertListEqual(
            Term(r"a??b\*or*and\?").split_wildcards(),
            ["a", "?", "", "?", r"b\*or", "*", r"and\?"],
            )
        self.assertListEqual(
            Term(r"\**\**").split_wildcards(),
            [r"\*", "*", r"\*", "*", ""],
            )

    def test_equality_proximty(self):
        """
        Regression test for a bug on approx equalities.

        .. todo:: Testing other tokens might be a good idea...
        """
        p1 = Proximity(term=Word('foo'), degree=5)
        p2 = Proximity(term=Word('bar'), degree=5)
        p3 = Proximity(term=Word('foo'), degree=5)
        p4 = Proximity(term=Word('foo'), degree=1)
        p5 = Proximity(term=Word('foo'), degree=None)

        self.assertNotEqual(p1, p2)
        self.assertEqual(p1, p3)
        self.assertNotEqual(p1, p4)
        self.assertEqual(p4, p5)

    def test_equality_fuzzy(self):
        f1 = Fuzzy(term=Word('foo'), degree=5)
        f2 = Fuzzy(term=Word('bar'), degree=5)
        f3 = Fuzzy(term=Word('foo'), degree=5)
        f4 = Fuzzy(term=Word('foo'), degree=.5)
        f5 = Fuzzy(term=Word('foo'), degree=None)

        self.assertNotEqual(f1, f2)
        self.assertEqual(f1, f3)
        self.assertNotEqual(f1, f4)
        self.assertEqual(f4, f5)

    def test_equality_boost(self):
        b1 = Boost(expr=Word('foo'), force=5)
        b2 = Boost(expr=Word('bar'), force=5)
        b3 = Boost(expr=Word('foo'), force=5)
        b4 = Boost(expr=Word('foo'), force=.5)

        self.assertNotEqual(b1, b2)
        self.assertEqual(b1, b3)
        self.assertNotEqual(b1, b4)

    def test_equality_range(self):
        r1 = Range(Word("20"), Word("40"), include_low=True, include_high=True)
        r2 = Range(Word("20"), Word("40"), include_low=True, include_high=True)
        self.assertEqual(r1, r2)

    def test_equality_range_different_terms(self):
        r1 = Range(Word("20"), Word("40"), include_low=True, include_high=True)
        self.assertNotEqual(r1, Range(Word("30"), Word("40"), include_low=True, include_high=True))
        self.assertNotEqual(r1, Range(Word("20"), Word("30"), include_low=True, include_high=True))

    def test_equality_range_different_bounds(self):
        """
        Regression test for a bug on range equalities.
        """
        r1 = Range(Word("20"), Word("40"), include_low=True, include_high=True)
        r2 = Range(Word("20"), Word("40"), include_low=False, include_high=True)
        r3 = Range(Word("20"), Word("40"), include_low=True, include_high=False)
        r4 = Range(Word("20"), Word("40"), include_low=False, include_high=False)
        self.assertNotEqual(r1, r2)
        self.assertNotEqual(r1, r3)
        self.assertNotEqual(r1, r4)
        self.assertNotEqual(r2, r3)
        self.assertNotEqual(r2, r4)
        self.assertNotEqual(r3, r4)

    def test_not_equality(self):
        # non regression test, adding a child should trigger non equality
        tree1 = OrOperation(Word("bar"))
        tree2 = OrOperation(Word("bar"), Word("foo"))
        self.assertNotEqual(tree1, tree2)


class SetChildrenTestCase(TestCase):

    def _test_set_children(self, item, children):
        item.children = children
        self.assertEqual(item.children, children)

    def test_set_children(self):
        test = self._test_set_children
        test(Word("foo"), [])
        test(Phrase('"foo"'), [])
        test(Regex("/foo/"), [])
        test(SearchField("foo", Word("bar")), [Word("baz")])
        test(Group(Word("foo")), [Word("foo")])
        test(FieldGroup(Word("foo")), [Word("foo")])
        test(Range(Word("20"), Word("30")), [Word("40"), Word("50")])
        test(Proximity(Word("foo")), [Word("foo")])
        test(Fuzzy(Word("foo")), [Word("foo")])
        test(Boost(Word("foo"), force=1), [Word("foo")])
        many_terms = tuple(Word(f"foo_{i}") for i in range(5))
        test(UnknownOperation(Word("foo"), Word("bar")), (Word("foo"), Word("bar")))
        test(UnknownOperation(*many_terms), many_terms)
        test(AndOperation(Word("foo"), Word("bar")), (Word("foo"), Word("bar")))
        test(AndOperation(*many_terms), many_terms)
        test(OrOperation(Word("foo"), Word("bar")), (Word("foo"), Word("bar")))
        test(OrOperation(*many_terms), many_terms)
        test(Plus(Word("foo")), [Word("foo")])
        test(Not(Word("foo")), [Word("foo")])
        test(Prohibit(Word("foo")), [Word("foo")])

    def _test_set_children_raises(self, item, children):
        with self.assertRaises(ValueError):
            item.children = children

    def test_set_children_raises(self):
        test = self._test_set_children_raises
        test(Word("foo"), [Word("foo")])
        test(Phrase('"foo"'), [Word("foo")])
        test(Regex("/foo/"), [Word("foo")])
        test(SearchField("foo", Word("bar")), [])
        test(SearchField("foo", Word("bar")), [Word("bar"), Word("baz")])
        test(Group(Word("foo")), [])
        test(Group(Word("foo")), [Word("foo"), Word("bar")])
        test(FieldGroup(Word("foo")), [])
        test(FieldGroup(Word("foo")), [Word("foo"), Word("bar")])
        test(Range(Word("20"), Word("30")), [])
        test(Range(Word("20"), Word("30")), [Word("20"), Word("30"), Word("40")])
        test(Proximity(Word("foo")), [])
        test(Proximity(Word("foo")), [Word("foo"), Word("bar")])
        test(Fuzzy(Word("foo")), [])
        test(Fuzzy(Word("foo")), [Word("foo"), Word("bar")])
        test(Boost(Word("foo"), force=1), [])
        test(Boost(Word("foo"), force=1), [Word("foo"), Word("bar")])
        test(Plus(Word("foo")), [])
        test(Plus(Word("foo")), [Word("foo"), Word("bar")])
        test(Not(Word("foo")), [])
        test(Not(Word("foo")), [Word("foo"), Word("bar")])
        test(Prohibit(Word("foo")), [])
        test(Prohibit(Word("foo")), [Word("foo"), Word("bar")])


class CloneTestCase(TestCase):

    def assert_equal_tail_head_pos(self, a, b):
        self.assertEqual(a.pos, b.pos)
        self.assertEqual(a.size, b.size)
        self.assertEqual(a.head, b.head)
        self.assertEqual(a.tail, b.tail)

    def test_word(self):
        orig = Word("foo", pos=3, head="\n", tail="\t")
        copy = orig.clone_item()
        self.assert_equal_tail_head_pos(orig, copy)
        self.assertEqual(orig.value, copy.value)
        self.assertEqual(orig, copy)

    def test_clone_kwargs_overrides(self):
        orig = Word("foo", pos=3, head="\n", tail="\t")
        copy = orig.clone_item(value="bar")
        self.assert_equal_tail_head_pos(orig, copy)
        self.assertEqual(copy.value, "bar")

    def test_phrase(self):
        orig = Phrase('"foo"', pos=3, head="\n", tail="\t")
        copy = orig.clone_item()
        self.assert_equal_tail_head_pos(orig, copy)
        self.assertEqual(orig.value, copy.value)
        self.assertEqual(orig, copy)

    def test_phrase_to_word(self):
        orig = Phrase('"foo"', pos=3, head="\n", tail="\t")
        copy = orig._clone_item(cls=Word)  # making the phase a word
        self.assert_equal_tail_head_pos(orig, copy)
        self.assertEqual(orig.value, copy.value)
        self.assertTrue(isinstance(copy, Word))

    def test_regex(self):
        orig = Regex("/foo/", pos=3, head="\n", tail="\t")
        copy = orig.clone_item()
        self.assert_equal_tail_head_pos(orig, copy)
        self.assertEqual(orig.value, copy.value)
        self.assertEqual(orig, copy)

    def test_search_field(self):
        orig = SearchField(name="foo", expr=Word("bar"), pos=3, head="\n", tail="\t")
        copy = orig.clone_item()
        self.assert_equal_tail_head_pos(orig, copy)
        self.assertEqual(orig.name, copy.name)
        self.assertEqual(copy.expr, NONE_ITEM)

        self.assertNotEqual(orig, copy)
        copy.children = [Word("bar")]
        self.assertEqual(orig, copy)

    def test_group(self):
        orig = Group(Word("bar"), pos=3, head="\n", tail="\t")
        copy = orig.clone_item()
        self.assert_equal_tail_head_pos(orig, copy)
        self.assertEqual(copy.expr, NONE_ITEM)

        self.assertNotEqual(orig, copy)
        copy.children = [Word("bar")]
        self.assertEqual(orig, copy)

    def test_field_group(self):
        orig = FieldGroup(Word("bar"), pos=3, head="\n", tail="\t")
        copy = orig.clone_item()
        self.assert_equal_tail_head_pos(orig, copy)
        self.assertEqual(copy.expr, NONE_ITEM)

        self.assertNotEqual(orig, copy)
        copy.children = [Word("bar")]
        self.assertEqual(orig, copy)

    def test_range(self):
        orig = Range(Word("foo"), Word("bar"), include_low=False, pos=3, head="\n", tail="\t")
        copy = orig.clone_item()
        self.assert_equal_tail_head_pos(orig, copy)
        self.assertEqual(orig.include_low, copy.include_low)
        self.assertEqual(orig.include_high, copy.include_high)
        self.assertEqual(copy.low, NONE_ITEM)
        self.assertEqual(copy.high, NONE_ITEM)

        self.assertNotEqual(orig, copy)
        copy.children = [Word("foo"), Word("bar")]
        self.assertEqual(orig, copy)

    def test_proximity(self):
        orig = Proximity(Word("bar"), degree=3, pos=3, head="\n", tail="\t")
        copy = orig.clone_item()
        self.assert_equal_tail_head_pos(orig, copy)
        self.assertEqual(orig.degree, copy.degree)
        self.assertEqual(copy.term, NONE_ITEM)

        self.assertNotEqual(orig, copy)
        copy.children = [Word("bar")]
        self.assertEqual(orig, copy)

    def test_fuzzy(self):
        orig = Fuzzy(Word("bar"), degree=.3, pos=3, head="\n", tail="\t")
        copy = orig.clone_item()
        self.assert_equal_tail_head_pos(orig, copy)
        self.assertEqual(orig.degree, copy.degree)
        self.assertEqual(copy.term, NONE_ITEM)

        self.assertNotEqual(orig, copy)
        copy.children = [Word("bar")]
        self.assertEqual(orig, copy)

    def test_boost(self):
        orig = Boost(Word("bar"), force=3.2, pos=3, head="\n", tail="\t")
        copy = orig.clone_item()
        self.assert_equal_tail_head_pos(orig, copy)
        self.assertEqual(orig.force, copy.force)
        self.assertEqual(copy.expr, NONE_ITEM)

        self.assertNotEqual(orig, copy)
        copy.children = [Word("bar")]
        self.assertEqual(orig, copy)

    def _test_operation(self, cls):
        orig = cls(Word("foo"), Word("bar"), Word("baz"), pos=3, head="\n", tail="\t")
        copy = orig.clone_item()
        self.assert_equal_tail_head_pos(orig, copy)
        self.assertEqual(copy.operands, ())

        self.assertNotEqual(orig, copy)
        copy.children = [Word("foo"), Word("bar"), Word("baz")]
        self.assertEqual(orig, copy)

    def test_unknown_operation(self):
        self._test_operation(UnknownOperation)

    def test_and_operation(self):
        self._test_operation(AndOperation)

    def test_or_operation(self):
        self._test_operation(OrOperation)

    def _test_unary(self, cls):
        orig = cls(Word("foo"), pos=3, head="\n", tail="\t")
        copy = orig.clone_item()
        self.assert_equal_tail_head_pos(orig, copy)
        self.assertEqual(copy.a, NONE_ITEM)

        self.assertNotEqual(orig, copy)
        copy.children = [Word("foo")]
        self.assertEqual(orig, copy)

    def test_plus(self):
        self._test_unary(Plus)

    def test_not(self):
        self._test_unary(Not)

    def test_prohibit(self):
        self._test_unary(Prohibit)


class TestTreeSpan(TestCase):

    def test_simple(self):
        self.assertEqual(Item(pos=0, size=3).span(), (0, 3))
        self.assertEqual(Item(head="\r", tail="\t\t", pos=1, size=3).span(), (1, 4))
        self.assertEqual(Item(head="\r", tail="\t\t", pos=1, size=3).span(head_tail=True), (0, 6))

    def test_none(self):
        self.assertEqual(Item(pos=None, size=3).span(), (None, None))
        self.assertEqual(Item(pos=None, size=3).span(head_tail=True), (None, None))

    def test_integration(self):
        tree = parser.parse(" foo:bar OR baz OR ([20 TO 2000] AND more:(yee AND yii)) ")
        self.assertEqual(tree.span(), (0, 57))
        self.assertEqual(tree.span(head_tail=True), (0, 57))
        foo, baz, group = tree.children
        self.assertEqual(foo.span(), (1, 9))
        self.assertEqual(foo.span(head_tail=True), (0, 9))
        self.assertEqual(baz.span(), (12, 15))
        self.assertEqual(baz.span(head_tail=True), (11, 16))
        self.assertEqual(group.span(), (19, 56))
        self.assertEqual(group.span(head_tail=True), (18, 57))
        bar, = foo.children
        self.assertEqual(bar.span(), (5, 8))
        self.assertEqual(bar.span(head_tail=True), (5, 9))
        andop, = group.children
        self.assertEqual(andop.span(), (20, 55))
        self.assertEqual(andop.span(head_tail=True), (20, 55))
        range_, more = andop.children
        self.assertEqual(range_.span(), (20, 32))
        self.assertEqual(range_.span(head_tail=True), (20, 33))
        self.assertEqual(more.span(), (37, 55))
        self.assertEqual(more.span(head_tail=True), (36, 55))
        field_group, = more.children
        self.assertEqual(field_group.span(), (42, 55))
        self.assertEqual(field_group.span(head_tail=True), (42, 55))
        and_op2, = field_group.children
        yee, yii = and_op2.children
        self.assertEqual(yee.span(), (43, 46))
        self.assertEqual(yee.span(head_tail=True), (43, 47))
        self.assertEqual(yii.span(), (51, 54))
        self.assertEqual(yii.span(head_tail=True), (50, 54))


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
        for letter in r'+-&|!(){}[]^"~*?:\\':
            with self.subTest("letter %s" % letter):
                query = r"\%stest" % letter
                tree = Word(query)
                unescaped = "%stest" % letter
                parsed = parser.parse(query)
                self.assertEqual(str(parsed), query)
                self.assertEqual(parsed, tree)
                self.assertEqual(parsed.unescaped_value, unescaped)

    def test_escaping_phrase(self):
        query = r'"test \"phrase"'
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

    def test_field_with_number(self):
        # non regression for issue #10
        tree = (
            SearchField(
                "field_42",
                Word("42")))
        parsed = parser.parse("field_42:42")
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
        with self.assertRaises(ParseError) as raised:
            parser.parse('foo:NOT')
        self.assertTrue(
            str(raised.exception).startswith("Syntax error in input : unexpected end of expr"))
        with self.assertRaises(ParseError) as raised:
            parser.parse('foo:AND')
        self.assertEqual(
            str(raised.exception),
            "Syntax error in input : unexpected  'AND' at position 4!",
        )
        with self.assertRaises(ParseError) as raised:
            parser.parse('foo:OR')
        self.assertEqual(
            str(raised.exception),
            "Syntax error in input : unexpected  'OR' at position 4!",
        )
        with self.assertRaises(ParseError) as raised:
            parser.parse('OR')
        self.assertEqual(
            str(raised.exception),
            "Syntax error in input : unexpected  'OR' at position 0!",
        )
        with self.assertRaises(ParseError) as raised:
            parser.parse('AND')
        self.assertEqual(
            str(raised.exception),
            "Syntax error in input : unexpected  'AND' at position 0!",
        )

    def test_parse_error_on_unmatched_parenthesis(self):
        with self.assertRaises(ParseError) as raised:
            parser.parse('((foo bar) ')
        self.assertTrue(
            str(raised.exception).startswith("Syntax error in input : unexpected end of expr"))

    def test_parse_error_on_unmatched_bracket(self):
        with self.assertRaises(ParseError) as raised:
            parser.parse('[foo TO bar')
        self.assertTrue(
            str(raised.exception).startswith("Syntax error in input : unexpected end of expr"))

    def test_parse_error_on_range(self):
        with self.assertRaises(ParseError) as raised:
            parser.parse('[foo TO ]')
        self.assertEqual(
            str(raised.exception),
            "Syntax error in input : unexpected  ']' at position 8!",
        )


class TestPrint(TestCase):

    def test_unknown_operation(self):
        tree = UnknownOperation(Word("foo", tail=" "), Word("bar", tail=" "), Word("baz"))
        self.assertEqual(str(tree), "foo bar baz")

    def test_fuzzy(self):
        item = Fuzzy(Word("foo"), degree=None)
        self.assertEqual(str(item), "foo~")
        self.assertEqual(repr(item), "Fuzzy(Word('foo'), 0.5)")
        self.assertEqual(item.degree, Decimal(".5").normalize())
        item = Fuzzy(Word("foo"), degree=".5")
        self.assertEqual(str(item), "foo~0.5")
        item = Fuzzy(Word("foo"), degree=str(1/3))
        self.assertEqual(str(item), "foo~0.3333333333333333")
        # head tail
        item = Fuzzy(Word("foo", head="\t", tail="\n"), head="\r", tail="  ")
        self.assertEqual(str(item), "\tfoo\n~")
        self.assertEqual(item.__str__(head_tail=True), "\r\tfoo\n~  ")

    def test_proximity(self):
        item = Proximity(Word("foo"), degree=None)
        self.assertEqual(str(item), "foo~")
        self.assertEqual(repr(item), "Proximity(Word('foo'), 1)")
        self.assertEqual(item.degree, 1)
        item = Proximity(Word("foo"), degree="1")
        self.assertEqual(str(item), "foo~1")
        self.assertEqual(repr(item), "Proximity(Word('foo'), 1)")
        item = Proximity(Word("foo"), degree="4")
        self.assertEqual(str(item), "foo~4")
        self.assertEqual(repr(item), "Proximity(Word('foo'), 4)")
        # head tail
        item = Proximity(Word("foo", head="\t", tail="\n"), head="\r", tail="  ")
        self.assertEqual(str(item), "\tfoo\n~")
        self.assertEqual(item.__str__(head_tail=True), "\r\tfoo\n~  ")

    def test_boost(self):
        item = Boost(Word("foo"), force="3")
        self.assertEqual(str(item), "foo^3")
        self.assertEqual(repr(item), "Boost(Word('foo'), 3)")
        item = Boost(Word("foo"), force=str(1/3))
        self.assertEqual(str(item), "foo^0.3333333333333333")
        # head tail
        item = Boost(Word("foo", head="\t", tail="\n"), force=2, head="\r", tail="  ")
        self.assertEqual(str(item), "\tfoo\n^2")
        self.assertEqual(item.__str__(head_tail=True), "\r\tfoo\n^2  ")

    def test_none_item(self):
        self.assertEqual(str(NONE_ITEM), "")
        self.assertEqual(str(AndOperation(NONE_ITEM, NONE_ITEM)), "AND")


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

    def test_with_unknown_op(self):
        prettify = Prettifier(indent=8, max_len=20)
        tree = UnknownOperation(
            Group(
                UnknownOperation(
                    Word("baaaaaaaaaar"),
                    Word("baaaaaaaaaaaaaz"))),
            Word("fooooooooooo"))
        self.assertEqual(
            "\n" + prettify(tree), """
(
        baaaaaaaaaar
        baaaaaaaaaaaaaz
)
fooooooooooo""")

    def test_with_unknown_op_nested(self):
        prettify = Prettifier(indent=8, max_len=20)
        tree = OrOperation(
            UnknownOperation(
                Word("baaaaaaaaaar"),
                Word("baaaaaaaaaaaaaz")),
            Word("fooooooooooo"))
        self.assertEqual(
            "\n" + prettify(tree), """
        baaaaaaaaaar
        baaaaaaaaaaaaaz
OR
fooooooooooo""")

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
        check = LuceneCheck(zeal=1)
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

    def test_zealous_or_not_prohibit(self):
        query = (
            OrOperation(
                Prohibit(Word("foo")),
                Word("bar")))
        check_zealous = LuceneCheck(zeal=1)
        self.assertFalse(check_zealous(query))
        self.assertIn("inconsistent", check_zealous.errors(query)[0])
        check_easy_going = LuceneCheck()
        self.assertTrue(check_easy_going(query))

    def test_zealous_or_not(self):
        query = (
            OrOperation(
                Not(Word("foo")),
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


class CheckVisitorTestCase(TestCase):

    NESTED_FIELDS = {
        'author': {
            'firstname': {},
            'book': {
                'title': {},
                'format': {
                    'type': {}
                }
            }
        },
        'collection.keywords': {  # nested field inside an object field
            'key': {},
            'more_info.linked': {  # again nested field inside an object field
                'key': {}
            },
        },
    }

    OBJECT_FIELDS = [
        'author.birth.city',
        'collection.title', 'collection.ref', 'collection.keywords.more_info.revision']

    SUB_FIELDS = [
        'foo.english',
        'author.book.title.raw',
    ]

    def setUp(self):
        self.checker = CheckNestedFields(nested_fields=self.NESTED_FIELDS)
        self.strict_checker = CheckNestedFields(
            nested_fields=self.NESTED_FIELDS,
            object_fields=self.OBJECT_FIELDS,
            sub_fields=self.SUB_FIELDS,
        )

    def test_correct_nested_lucene_query_column_not_raise(self):
        tree = parser.parse('author:book:title:"foo" AND '
                            'author:book:format:type: "pdf"')
        self.strict_checker(tree)

    def test_correct_object_lucene_query_column_not_raise(self):
        tree = parser.parse('author:birth:city:"foo" AND '
                            'collection:(ref:"foo" AND title:"bar")')
        self.strict_checker(tree)
        self.checker(tree)
        self.assertIsNotNone(tree)

    def test_correct_subfield_lucene_query_column_not_raises(self):
        tree = parser.parse('foo:english:"foo" AND '
                            'author:book:title:raw:"pdf"')
        self.strict_checker(tree)

    def test_correct_nested_lucene_query_with_point_not_raise(self):
        tree = parser.parse('author.book.title:"foo" AND '
                            'author.book.format.type:"pdf"')
        self.strict_checker(tree)
        self.assertIsNotNone(tree)

    def test_correct_object_lucene_query_with_point_not_raise(self):
        tree = parser.parse('author.birth.city:"foo" AND '
                            'collection.ref:"foo"')
        self.strict_checker(tree)
        self.checker(tree)
        self.assertIsNotNone(tree)

    def test_correct_subfield_lucene_query_with_point_not_raises(self):
        tree = parser.parse('foo.english:"foo" AND '
                            'author.book.title.raw:"pdf"')
        self.strict_checker(tree)

    def test_correct_object_mix_do_not_raise(self):
        tree = parser.parse('author:(birth.city:"foo" AND book.title:"bar")')
        self.strict_checker(tree)
        self.checker(tree)
        self.assertIsNotNone(tree)

    def test_incorrect_nested_lucene_query_column_raise(self):
        tree = parser.parse('author:gender:"Mr" AND '
                            'author:book:format:type:"pdf"')
        with self.assertRaises(ObjectSearchFieldException) as e:
            self.strict_checker(tree)
        self.assertIn('author.gender', str(e.exception))

    def test_incorrect_nested_lucene_query_with_point_raise(self):
        tree = parser.parse('author.gender:"Mr" AND '
                            'author.book.format.type:"pdf"')
        with self.assertRaises(ObjectSearchFieldException) as e:
            self.strict_checker(tree)
        self.assertIn('"author.gender"', str(e.exception))

    def test_correct_nested_lucene_query_with_and_column_not_raise(self):
        tree = parser.parse(
            'author:(book.title:"foo" OR book.title:"bar")')
        self.checker(tree)
        self.assertIsNotNone(tree)

    def test_complex_subfield_not_raises(self):
        tree = parser.parse(
            'author:(book.title.raw:"foo" OR book.title.raw:"bar")')
        self.checker(tree)
        self.assertIsNotNone(tree)

    def test_simple_query_with_a_nested_field_should_raise(self):
        tree = parser.parse('author:"foo"')
        with self.assertRaises(NestedSearchFieldException) as e:
            self.strict_checker(tree)
        self.assertIn('"author"', str(e.exception))

    def test_simple_query_with_a_multi_nested_field_should_raise(self):
        tree = parser.parse('author:book:"foo"')
        with self.assertRaises(NestedSearchFieldException) as e:
            self.strict_checker(tree)
        self.assertIn('"author.book"', str(e.exception))

    def test_complex_query_with_a_multi_nested_field_should_raise(self):
        tree = parser.parse('author:test OR author.firstname:"Hugo"')
        with self.assertRaises(NestedSearchFieldException) as e:
            self.strict_checker(tree)
        self.assertIn('"author"', str(e.exception))

    def test_complex_query_column_with_a_multi_nested_field_should_raise(self):
        tree = parser.parse('author:("test" AND firstname:Hugo)')
        with self.assertRaises(NestedSearchFieldException) as e:
            self.strict_checker(tree)
        self.assertIn('"author"', str(e.exception))

    def test_complex_mix(self):
        tree = parser.parse(
            'collection:(title:"foo" AND keywords.more_info:(linked.key:"bar" revision:"test"))')
        self.strict_checker(tree)
        self.checker(tree)
        self.assertIsNotNone(tree)

    def test_complex_mix_raise(self):
        tree = parser.parse(
            'collection:(title:"foo" AND keywords.more_info:(linked:"bar" revision:"test"))')
        with self.assertRaises(NestedSearchFieldException) as e:
            self.strict_checker(tree)
        self.assertIn('"collection.keywords.more_info.linked"', str(e.exception))
        self.assertIsNotNone(tree)

    def test_incomplete_object_field_raise(self):
        tree = parser.parse('collection.keywords.more_info:"foo"')
        with self.assertRaises(NestedSearchFieldException) as e:
            self.strict_checker(tree)
        self.assertIn('"collection.keywords.more_info"', str(e.exception))

        tree = parser.parse('author:birth:"foo"')
        with self.assertRaises(NestedSearchFieldException) as e:
            self.strict_checker(tree)
        self.assertIn('"author.birth"', str(e.exception))


class UnknownOperationResolverTestCase(TestCase):

    def test_and_resolution(self):
        tree = (
            UnknownOperation(
                Word("a"),
                Word("b"),
                OrOperation(Word("c"), Word("d"))))
        expected = (
            AndOperation(
                Word("a"),
                Word("b"),
                OrOperation(Word("c"), Word("d"))))
        resolver = UnknownOperationResolver(resolve_to=AndOperation)
        self.assertEqual(resolver(tree), expected)

    def test_or_resolution(self):
        tree = (
            UnknownOperation(
                Word("a"),
                Word("b"),
                AndOperation(Word("c"), Word("d"))))
        expected = (
            OrOperation(
                Word("a"),
                Word("b"),
                AndOperation(Word("c"), Word("d"))))
        resolver = UnknownOperationResolver(resolve_to=OrOperation)
        self.assertEqual(resolver(tree), expected)

    def test_lucene_resolution_simple(self):
        tree = (
            UnknownOperation(
                Word("a"),
                Word("b"),
                UnknownOperation(Word("c"), Word("d"))))
        expected = (
            AndOperation(
                Word("a"),
                Word("b"),
                AndOperation(Word("c"), Word("d"))))
        resolver = UnknownOperationResolver(resolve_to=None)
        self.assertEqual(resolver(tree), expected)

    def test_lucene_resolution_last_op(self):
        tree = (
            OrOperation(
                Word("a"),
                Word("b"),
                UnknownOperation(Word("c"), Word("d")),
                AndOperation(
                    Word("e"),
                    UnknownOperation(Word("f"), Word("g"))),
                UnknownOperation(Word("i"), Word("j")),
                OrOperation(
                    Word("k"),
                    UnknownOperation(Word("l"), Word("m"))),
                UnknownOperation(Word("n"), Word("o"))))
        expected = (
            OrOperation(
                Word("a"),
                Word("b"),
                OrOperation(Word("c"), Word("d")),
                AndOperation(
                    Word("e"),
                    AndOperation(Word("f"), Word("g"))),
                AndOperation(Word("i"), Word("j")),
                OrOperation(
                    Word("k"),
                    OrOperation(Word("l"), Word("m"))),
                OrOperation(Word("n"), Word("o"))))
        resolver = UnknownOperationResolver(resolve_to=None)
        self.assertEqual(resolver(tree), expected)

    def test_lucene_resolution_last_op_with_group(self):
        tree = (
            OrOperation(
                Word("a"),
                Word("b"),
                Group(
                    AndOperation(
                        Word("c"),
                        UnknownOperation(Word("d"), Word("e")))),
                UnknownOperation(Word("f"), Word("g")),
                Group(
                    UnknownOperation(Word("h"), Word("i")))))
        expected = (
            OrOperation(
                Word("a"),
                Word("b"),
                Group(
                    AndOperation(
                        Word("c"),
                        AndOperation(Word("d"), Word("e")))),
                OrOperation(Word("f"), Word("g")),
                Group(
                    AndOperation(Word("h"), Word("i")))))
        resolver = UnknownOperationResolver(resolve_to=None)
        self.assertEqual(resolver(tree), expected)

    def test_resolve_to_verification(self):
        with self.assertRaises(ValueError):
            UnknownOperationResolver(resolve_to=object())

    def test_head_tail_pos(self):
        tree = parser.parse("\ra\nb (c\t (d e f)) ")
        resolver = UnknownOperationResolver(resolve_to=None)
        transformed = resolver(tree)
        self.assertEqual(str(transformed), "\ra\nAND b AND (c\t AND (d AND e AND f)) ")
        self.assertEqual(transformed.pos, tree.pos)
        self.assertEqual(transformed.size, tree.size)
        and_op, orig_op = transformed.children[2].children[0], tree.children[2].children[0]
        self.assertEqual(type(and_op), AndOperation)
        self.assertEqual(and_op.pos, orig_op.pos)
        self.assertEqual(and_op.size, orig_op.size)
        and_op, orig_op = and_op.children[1].children[0], orig_op.children[1].children[0]
        self.assertEqual(type(and_op), AndOperation)
        self.assertEqual(and_op.pos, orig_op.pos)
        self.assertEqual(and_op.size, orig_op.size)

        resolver = UnknownOperationResolver(resolve_to=OrOperation)
        transformed = resolver(tree)
        self.assertEqual(str(transformed), "\ra\nOR b OR (c\t OR (d OR e OR f)) ")
