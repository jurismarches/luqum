# -*- coding: utf-8 -*-
from unittest import TestCase

from luqum.tree import (
    SearchField, FieldGroup, Group, Word, Phrase, Proximity, Fuzzy, Range,
    Not, AndOperation, OrOperation, Plus, UnknownOperation)
from luqum.auto_head_tail import auto_head_tail


class AutoHeadTailTestCase(TestCase):

    def test_or_operation(self):
        tree = OrOperation(Word("foo"), Word("bar"), Word("baz"))
        self.assertEqual(str(tree), "fooORbarORbaz")
        self.assertEqual(str(auto_head_tail(tree)), "foo OR bar OR baz")

    def test_and_operation(self):
        tree = AndOperation(Word("foo"), Word("bar"), Word("baz"))
        self.assertEqual(str(tree), "fooANDbarANDbaz")
        self.assertEqual(str(auto_head_tail(tree)), "foo AND bar AND baz")

    def test_unknown_operation(self):
        tree = UnknownOperation(Word("foo"), Word("bar"), Word("baz"))
        self.assertEqual(str(tree), "foobarbaz")
        self.assertEqual(str(auto_head_tail(tree)), "foo bar baz")

    def test_range(self):
        tree = Range(Word("foo"), Word("bar"))
        self.assertEqual(str(tree), "[fooTObar]")
        self.assertEqual(str(auto_head_tail(tree)), "[foo TO bar]")

    def test_not(self):
        tree = Not(Word("foo"))
        self.assertEqual(str(tree), "NOTfoo")
        self.assertEqual(str(auto_head_tail(tree)), "NOT foo")

    def test_complex(self):
        tree = Group(
            OrOperation(
                SearchField(
                    "foo",
                    FieldGroup(UnknownOperation(Word("bar"), Range(Word("baz"), Word("spam")))),
                ),
                Not(Proximity(Phrase('"ham ham"'), 2)),
                Plus(Fuzzy(Word("hammer"), 3)),
            )
        )
        self.assertEqual(str(tree), '(foo:(bar[bazTOspam])ORNOT"ham ham"~2OR+hammer~3)')
        self.assertEqual(
            str(auto_head_tail(tree)),
            '(foo:(bar [baz TO spam]) OR NOT "ham ham"~2 OR +hammer~3)',
        )
        # idem potent
        self.assertEqual(
            str(auto_head_tail(auto_head_tail(tree))),
            '(foo:(bar [baz TO spam]) OR NOT "ham ham"~2 OR +hammer~3)',
        )

    def test_auto_head_tail_no_change_to_existing(self):
        tree = AndOperation(
            Range(Word("foo", tail="\t"), Word("bar", head="\n"), tail="\r"),
            Not(Word("baz", head="\t\t"), head="\n\n", tail="\r\r"),
            Word("spam", head="\t\n"),
        )
        self.assertEqual(str(tree), "[foo\tTO\nbar]\rAND\n\nNOT\t\tbaz\r\rAND\t\nspam")
        self.assertEqual(
            str(auto_head_tail(tree)),
            "[foo\tTO\nbar]\rAND\n\nNOT\t\tbaz\r\rAND\t\nspam"
        )
