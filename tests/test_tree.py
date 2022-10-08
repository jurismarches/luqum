from decimal import Decimal
from unittest import TestCase

from luqum.parser import parser
from luqum.tree import (
    SearchField, FieldGroup, Group, Item,
    Term, Word, Phrase, Regex, Proximity, Fuzzy, Boost, Range,
    NONE_ITEM, Not, AndOperation, OrOperation, Plus, Prohibit, UnknownOperation)


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
        # the \ itself can be escaped !
        self.assertTrue(Term(r"\\*\\?").has_wildcard())

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
