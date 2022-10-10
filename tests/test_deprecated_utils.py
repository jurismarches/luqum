# -*- coding: utf-8 -*-
"""
.. todo:: split this file in multiple file: tree, lexer, parser
"""
import collections
import copy
from unittest import TestCase

from luqum.tree import Group, Word, Phrase, AndOperation, OrOperation
from luqum.deprecated_utils import LuceneTreeVisitor, LuceneTreeTransformer, LuceneTreeVisitorV2


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
        self.assertEqual(list(result), ['a OR b', 'a', 'b'])

        tree = AndOperation(Word('a'), Word('b'))
        result = visitor.visit(tree)
        self.assertEqual(list(result), ['a BASE_OP b', 'a', 'b'])


class TreeTransformerTestCase(TestCase):

    class BasicTransformer(LuceneTreeTransformer):
        """
        Dummy transformer that simply turn any Word node's value into "lol"
        """
        def visit_word(self, node, parent):
            return Word('lol')

        def visit_phrase(self, node, parent):
            return None

    class OrListOperation(OrOperation):
        """Dummy operation having list operands instead of tuple
        """
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.operands = list(self.operands)

    def test_basic_traversal(self):
        tree = (
            AndOperation(
                Word("foo"),
                Word("bar")))

        transformer = self.BasicTransformer()
        new_tree = transformer.visit(tree)

        self.assertEqual(
            new_tree,
            (AndOperation(
                Word("lol"),
                Word("lol"))))

    def test_no_transform(self):
        tree = AndOperation()
        transformer = self.BasicTransformer()
        new_tree = transformer.visit(tree)
        self.assertEqual(
            new_tree,
            AndOperation())

    def test_one_word(self):
        tree = Word("foo")
        transformer = self.BasicTransformer()
        new_tree = transformer.visit(tree)
        self.assertEqual(
            new_tree,
            Word("lol"))

    def test_removal(self):
        tree = (
            AndOperation(
                AndOperation(
                    Word("foo"),
                    Phrase('"bar"')),
                AndOperation(
                    Phrase('"baz"'),
                    Phrase('"biz"'))))

        transformer = self.BasicTransformer()
        new_tree = transformer.visit(tree)

        self.assertEqual(
            new_tree,
            (AndOperation(
                AndOperation(Word("lol")),
                AndOperation())))

    def test_operands_list(self):
        OrListOperation = self.OrListOperation
        tree = (
            OrListOperation(
                OrListOperation(
                    Word("foo"),
                    Phrase('"bar"')),
                OrListOperation(
                    Phrase('"baz"'))))

        transformer = self.BasicTransformer()
        new_tree = transformer.visit(tree)

        self.assertEqual(
            new_tree,
            (OrListOperation(
                OrListOperation(Word("lol")),
                OrListOperation())))

    def test_silent_value_error(self):
        # in the case some attribute mislead the search for node do not raise
        tree = AndOperation(Word("a"), Word("b"))
        setattr(tree, "misleading1", ())
        setattr(tree, "misleading2", [])
        # hackishly patch __dict__ to be sure we have operands in right order for test
        tree.__dict__ = collections.OrderedDict(tree.__dict__)
        tree.__dict__['operands'] = tree.__dict__.pop('operands')  # operands are now last

        transformer = self.BasicTransformer()
        new_tree = transformer.visit(tree)

        self.assertEqual(
            new_tree,
            AndOperation(Word("lol"), Word("lol")))

    def test_repeating_expression(self):
        # non regression test
        tree = AndOperation(
            Group(OrOperation(Word('bar'), Word('foo'))),
            Group(OrOperation(Word('bar'), Word('foo'), Word('spam'))),
        )
        # basic transformer should not change tree
        same_tree = LuceneTreeTransformer().visit(copy.deepcopy(tree))
        self.assertEqual(same_tree, tree)


class TreeVisitorV2TestCase(TestCase):

    class BasicVisitor(LuceneTreeVisitorV2):
        """ Dummy visitor, simply yielding a list of nodes. """
        def generic_visit(self, node, parents, context):
            yield node
            for c in node.children:
                yield from self.visit(c, parents + [node], context)

    class MROVisitor(LuceneTreeVisitorV2):

        def visit_or_operation(self, node, parents=[], context=None):
            return "{} OR {}".format(*[self.visit(c) for c in node.children])

        def visit_base_operation(self, node, parents=[], context=None):
            return "{} BASE_OP {}".format(*[self.visit(c) for c in node.children])

        def visit_word(self, node, parents=[], context=None):
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
        self.assertEqual(result, 'a OR b')

        tree = OrOperation(AndOperation(Word('a'), Word('b')), Word('c'))
        result = visitor.visit(tree)
        self.assertEqual(result, 'a BASE_OP b OR c')

    def test_generic_visit_fails_by_default(self):
        visitor = self.MROVisitor()
        with self.assertRaises(AttributeError):
            visitor.visit(Phrase('"test"'))
