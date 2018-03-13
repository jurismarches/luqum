# -*- coding: utf-8 -*-
from unittest import TestCase

from ..naming import get_name, set_name, auto_name, name_index, extract
from ..parser import parser
from ..tree import (
    AndOperation, OrOperation, UnknownOperation, SearchField,
    Fuzzy, Proximity, Word, Phrase, Range, Group)


class AutoNameTestCase(TestCase):

    def test_auto_name_one_term(self):
        tree = Word("test")
        auto_name(tree)
        self.assertEqual(get_name(tree), "0")

        tree = Phrase('"test"')
        auto_name(tree)
        self.assertEqual(get_name(tree), "0")

        tree = Range("test", "*")
        auto_name(tree)
        self.assertEqual(get_name(tree), "0")

    def test_auto_name_simple_op(self):
        for OpCls in AndOperation, OrOperation, UnknownOperation:
            with self.subTest("operation %r" % OpCls):
                tree = OpCls(
                    Word("test"),
                    Phrase('"test"'),
                )
                auto_name(tree)
                self.assertEqual(get_name(tree), "0")
                self.assertEqual(get_name(tree.children[0]), "0_0")
                self.assertEqual(get_name(tree.children[1]), "0_1")

    def test_auto_name_nested(self):
        tree = AndOperation(
            OrOperation(
                SearchField("bar", Word("test")),
                AndOperation(
                    Proximity(Phrase('"test"'), 2),
                    SearchField("baz", Word("test")),
                ),
            ),
            Group(
                UnknownOperation(
                    Fuzzy(Word("test")),
                    Phrase('"test"'),
                ),
            ),
        )

        auto_name(tree)
        # and
        and1 = tree
        self.assertEqual(get_name(and1), "0")
        # - or
        or1 = and1.children[0]
        self.assertEqual(get_name(or1), "0_0")
        # --- search field word
        sfield1 = or1.children[0]
        self.assertFalse(get_name(sfield1))
        self.assertEqual(get_name(sfield1.expr), "0_0_0")
        # --- and
        and2 = or1.children[1]
        self.assertEqual(get_name(and2), "0_0_1")
        # ----- proximity phrase
        self.assertEqual(get_name(and2.children[0].term), "0_0_1_0")
        # ----- search field word
        sfield2 = and2.children[1]
        self.assertFalse(get_name(sfield2))
        self.assertEqual(get_name(sfield2.expr), "0_0_1_1")
        # - group
        group1 = and1.children[1]
        self.assertEqual(get_name(group1), None)
        # --- unknown op
        unknownop1 = group1.children[0]
        self.assertEqual(get_name(unknownop1), "0_1")
        # ----- fuzzy word
        self.assertEqual(get_name(unknownop1.children[0].term), "0_1_0")
        # ----- phrase
        self.assertEqual(get_name(unknownop1.children[1]), "0_1_1")


class NameIndexTestCase(TestCase):

    def test_name_index_simple_term(self):
        tree = Word("bar")
        set_name(tree, "0")
        self.assertEqual(name_index(tree), {"0": (0, len(str(tree)))})

        phrase = Phrase('"baz"')
        tree = Group(phrase)
        set_name(phrase, "0")
        self.assertEqual(name_index(tree), {"0": (1, len(str(phrase)))})
        set_name(phrase, "funny")
        self.assertEqual(name_index(tree), {"funny": (1, len(str(phrase)))})

    def test_name_index_nested(self):
        # we use parsing for this way, it's more evident to see index is right
        expr = 'bar:baz OR (foo~2 AND "foo bar") OR spam:(bazz dazz)'

        tree = parser.parse(expr)
        self.assertEqual(str(tree), expr)  # needs to be sure

        root_or = tree
        bar_search_field = tree.children[0]
        baz = bar_search_field.expr
        and_op = tree.children[1].children[0]
        foo = and_op.children[0].term
        foo_bar = and_op.children[1]
        spam_search_field = tree.children[2]
        unknown_op = spam_search_field.expr.children[0]
        bazz = unknown_op.children[0]
        dazz = unknown_op.children[1]
        set_name(root_or, "root_or")
        set_name(baz, "baz")
        set_name(and_op, "and_op")
        set_name(foo, "foo")
        set_name(foo_bar, "foo_bar")
        set_name(unknown_op, "unknown_op")
        set_name(bazz, "bazz")
        set_name(dazz, "dazz")

        result = name_index(tree)

        def _extract(name):
            return extract(expr, name, result)

        self.assertEqual(_extract("root_or"), expr)
        self.assertEqual(_extract("baz"), "baz")
        self.assertEqual(_extract("and_op"), 'foo~2 AND "foo bar"')
        self.assertEqual(_extract("foo"), "foo")
        self.assertEqual(_extract("foo_bar"), '"foo bar"')
        self.assertEqual(_extract("unknown_op"), "bazz dazz")
        self.assertEqual(_extract("bazz"), "bazz")
        self.assertEqual(_extract("dazz"), "dazz")

    def test_name_index_nested2(self):
        # an expression where outer node does not have a name
        expr = '(objet:(bar OR (foo AND "foo bar")))'

        tree = parser.parse(expr)
        self.assertEqual(str(tree), expr)  # needs to be sure

        or_op = tree.expr.expr.expr  # group, field, fieldgroup
        bar = or_op.operands[0]
        and_op = or_op.operands[1].expr
        foo = and_op.operands[0]
        foo_bar = and_op.operands[1]
        set_name(or_op, "or_op")
        set_name(bar, "bar")
        set_name(and_op, "and_op")
        set_name(foo, "foo")
        set_name(foo_bar, "foo_bar")

        result = name_index(tree)

        def _extract(name):
            return extract(expr, name, result)

        self.assertEqual(_extract("or_op"), 'bar OR (foo AND "foo bar")')
        self.assertEqual(_extract("bar"), "bar")
        self.assertEqual(_extract("and_op"), 'foo AND "foo bar"')
        self.assertEqual(_extract("foo"), "foo")
        self.assertEqual(_extract("foo_bar"), '"foo bar"')
