from unittest import TestCase

from luqum.parser import parser
from luqum.tree import (Group, Word, AndOperation, OrOperation, BoolOperation,
                        UnknownOperation, Prohibit, Plus, From, To, Range, SearchField,
                        Boost)
from luqum.utils import UnknownOperationResolver, OpenRangeTransformer


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

    def test_lucene_resolution_bool(self):
        tree = parser.parse("a b (+f +g) -(c d) +e")
        expected = (
            BoolOperation(
                Word("a"),
                Word("b"),
                Group(BoolOperation(Plus(Word("f")), Plus(Word("g")))),
                Prohibit(Group(BoolOperation(Word("c"), Word("d")))),
                Plus(Word('e'))))
        resolver = UnknownOperationResolver(resolve_to=BoolOperation)
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


class OpenRangeTransformerTestCase(TestCase):
    def test_simple_resolution_from(self):
        tree = (
            From(Word("1"), True)
        )
        expected = (
            Range(Word("1", tail=" "), Word("*", head=" "), True, True)
        )
        for merge_ranges in (True, False):
            with self.subTest(merge_ranges=merge_ranges):
                resolver = OpenRangeTransformer(merge_ranges=merge_ranges)
                output = resolver(tree)
                self.assertEqual(output, expected)
                self.assertEqual(str(output), str(expected))

    def test_simple_resolution_to(self):
        tree = (
            To(Word("1"), False)
        )
        expected = (
            Range(Word("*", tail=" "), Word("1", head=" "), True, False)
        )
        for merge_ranges in (True, False):
            with self.subTest(merge_ranges=merge_ranges):
                resolver = OpenRangeTransformer(merge_ranges=merge_ranges)
                output = resolver(tree)
                self.assertEqual(output, expected)
                self.assertEqual(str(output), str(expected))

    def test_and_resolution(self):
        tree = (
            AndOperation(
                From(Word("1"), True),
                To(Word("2"), True),
            )
        )
        expected = (
            AndOperation(
                Range(Word("1", tail=" "), Word("2", head=" "), True, True)
            )
        )
        resolver = OpenRangeTransformer(merge_ranges=True)
        output = resolver(tree)
        self.assertEqual(output, expected)
        self.assertEqual(str(output), str(expected))

    def test_and_resolution_without_merge(self):
        tree = (
            AndOperation(
                From(Word("1"), True),
                To(Word("2"), True),
            )
        )
        expected = (
            AndOperation(
                Range(Word("1", tail=" "), Word("*", head=" "), True),
                Range(Word("*", tail=" "), Word("2", head=" "), True),
            )
        )
        resolver = OpenRangeTransformer(merge_ranges=False)
        output = resolver(tree)
        self.assertEqual(output, expected)
        self.assertEqual(str(output), str(expected))

    def test_unjoined_resolution(self):
        tree = (
            AndOperation(
                From(Word("1"), False),
                From(Word("2"), True),
            )
        )
        expected = (
            AndOperation(
                Range(Word("1", tail=" "), Word("*", head=" "), False, True),
                Range(Word("2", tail=" "), Word("*", head=" "), True, True)
            )
        )
        resolver = OpenRangeTransformer(merge_ranges=True)
        output = resolver(tree)
        self.assertEqual(output, expected)
        self.assertEqual(str(output), str(expected))

    def test_normal_ranges_are_untouched(self):
        tree = (
            AndOperation(
                Range(Word("1"), Word("2"), True, True),
                Range(Word("*"), Word("*"), True, True),
                Range(Word("1"), Word("*"), True, True),
            )
        )
        for merge_ranges in (True, False):
            with self.subTest(merge_ranges=merge_ranges):
                resolver = OpenRangeTransformer(merge_ranges=merge_ranges)
                output = resolver(tree)
                self.assertEqual(output, tree)

    def test_first_range_is_merged(self):
        tree = (
            AndOperation(
                Range(Word("*"), Word("2"), True, True),
                Range(Word("*"), Word("*"), True, True),
                Range(Word("*"), Word("3"), True, True),
                Range(Word("1"), Word("*"), True, True),
                Range(Word("4"), Word("*"), True, True),
            )
        )
        expected = (
            AndOperation(
                Range(Word("1"), Word("2"), True, True),
                Range(Word("*"), Word("*"), True, True),
                Range(Word("4"), Word("3"), True, True),
            )
        )
        resolver = OpenRangeTransformer(merge_ranges=True)
        output = resolver(tree)
        self.assertEqual(output, expected)
        self.assertEqual(str(output), str(expected))

    def test_do_not_merge_unknown(self):
        tree = (
            UnknownOperation(
                Range(Word("1"), Word("*"), True, True),
                Range(Word("*"), Word("2"), True, True),
            )
        )
        resolver = OpenRangeTransformer(merge_ranges=True)
        output = resolver(tree)
        self.assertEqual(output, tree)

    def test_do_not_merge_searchfield(self):
        tree = (
            AndOperation(
                Range(Word("1"), Word("*"), True, True),
                SearchField("foo", Range(Word("*"), Word("2"), True, True))
            )
        )
        resolver = OpenRangeTransformer(merge_ranges=True)
        output = resolver(tree)
        self.assertEqual(output, tree)

    def test_do_not_merge_boosted(self):
        tree = (
            AndOperation(
                Boost(Range(Word("1"), Word("*"), True, True), 2),
                Boost(Range(Word("*"), Word("2"), True, True), 2),
            )
        )
        resolver = OpenRangeTransformer(merge_ranges=True)
        output = resolver(tree)
        self.assertEqual(output, tree)
