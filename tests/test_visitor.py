import collections
import copy
from unittest import TestCase

from luqum.tree import (
    NONE_ITEM, Group, Word, Phrase, AndOperation, OrOperation, Proximity, SearchField,
    Boost, Fuzzy, Regex,
)
from luqum.visitor import (
    PathTrackingTransformer, PathTrackingVisitor, TreeTransformer, TreeVisitor,
)


class TreeVisitorTestCase(TestCase):

    class BasicVisitor(TreeVisitor):
        """Dummy visitor, simply yielding a list of nodes. """

        def generic_visit(self, node, context):
            yield node
            yield from super().generic_visit(node, context)

    class TrackingParentsVisitor(TreeVisitor):
        """Visitor, yielding nodes and parents."""

        def generic_visit(self, node, context):
            yield node, context.get("parents")
            yield from super().generic_visit(node, context)

    class MROVisitor(TreeVisitor):

        def visit_or_operation(self, node, context):
            yield "{} OR {}".format(*node.children)
            yield from super().generic_visit(node, context)

        def visit_base_operation(self, node, context):
            yield "{} BASE_OP {}".format(*node.children)
            yield from super().generic_visit(node, context)

        def visit_word(self, node, parents=[]):
            yield node.value

    def test_generic_visit(self):
        tree = AndOperation(Word("foo"), Word("bar"))
        visitor = TreeVisitor()
        nodes = visitor.visit(tree)
        self.assertEqual(nodes, [])
        # with a context for coverage…
        nodes = visitor.visit(tree, context={})
        self.assertEqual(nodes, [])

    def test_basic_traversal(self):
        tree = AndOperation(Word("foo"), Word("bar"))
        visitor = self.BasicVisitor()
        nodes = visitor.visit(tree)
        self.assertListEqual([tree, Word("foo"), Word("bar")], nodes)

    def test_parents_tracking(self):
        tree = AndOperation(Word("foo"), Proximity(Phrase('"bar"'), 2))
        visitor = self.TrackingParentsVisitor(track_parents=True)
        nodes = visitor.visit(tree)
        self.assertListEqual(
            [
                (tree, None),
                (Word("foo"), (tree,)),
                (Proximity(Phrase('"bar"'), degree=2), (tree,)),
                (Phrase('"bar"'), (tree, Proximity(Phrase('"bar"'), 2))),
            ],
            nodes,
        )

    def test_parents_tracking_no_tracking(self):
        tree = AndOperation(Word("foo"), Phrase('"bar"'))
        # no parents tracking !
        visitor = self.TrackingParentsVisitor()
        nodes = visitor.visit(tree)
        self.assertListEqual([(tree, None), (Word("foo"), None), (Phrase('"bar"'), None)], nodes)

    def test_mro(self):
        visitor = self.MROVisitor()

        tree = OrOperation(Word('a'), Word('b'))
        result = visitor.visit(tree)
        self.assertEqual(list(result), ['a OR b', 'a', 'b'])

        # AndOperation has no specific method,
        # but inherists BaseOperation, hence uses visit_base_operation
        tree = AndOperation(Word('a'), Word('b'))
        result = visitor.visit(tree)
        self.assertEqual(list(result), ['a BASE_OP b', 'a', 'b'])


class TreeTransformerTestCase(TestCase):

    class BasicTransformer(TreeTransformer):
        """
        Dummy transformer that simply turn any Word node's value into "lol"
        """
        def visit_word(self, node, context):
            yield Word(context.get("replacement", 'lol'))

        def visit_phrase(self, node, context):
            yield from []

        def visit_base_operation(self, node, context):
            new_node, = super().generic_visit(node, context)
            # if new_node has no operands, it's like a removal
            if len(new_node.children) == 0:
                return
            # if we have only one operands return it
            elif len(new_node.children) == 1:
                yield new_node.children[0]
            else:
                # normal return
                yield new_node

    class TrackingParentsTransformer(TreeTransformer):

        def visit_word(self, node, context):
            new_node, = self.generic_visit(node, context)
            if any(isinstance(p, SearchField) for p in context["new_parents"]):
                new_node.value = "lol"
            yield new_node

    class RaisingTreeTransformer(TreeTransformer):

        def generic_visit(self, node, context):
            yield node
            yield node

    class RaisingTreeTransformer2(TreeTransformer):

        def generic_visit(self, node, context):
            raise ValueError("Random error")

    def test_basic_traversal(self):
        tree = AndOperation(Word("foo"), Word("bar"))

        transformer = self.BasicTransformer()
        new_tree = transformer.visit(tree)
        self.assertEqual(new_tree, AndOperation(Word("lol"), Word("lol")))

    def test_context_value(self):
        tree = AndOperation(Word("foo"), Word("bar"))

        transformer = self.BasicTransformer()
        new_tree = transformer.visit(tree, context={"replacement": "rotfl"})
        self.assertEqual(new_tree, AndOperation(Word("rotfl"), Word("rotfl")))

    def test_no_transform(self):
        tree = AndOperation(NONE_ITEM, NONE_ITEM)
        transformer = self.BasicTransformer()
        new_tree = transformer.visit(tree)
        self.assertEqual(new_tree, tree)

    def test_one_word(self):
        tree = Word("foo")
        transformer = self.BasicTransformer()
        new_tree = transformer.visit(tree)
        self.assertEqual(new_tree, Word("lol"))

    def test_tracking_parents(self):
        tree = OrOperation(Word("foo"), SearchField("test", Word("bar")))
        expected = OrOperation(Word("foo"), SearchField("test", Word("lol")))
        transformer = self.TrackingParentsTransformer(track_new_parents=True)
        new_tree = transformer.visit(tree)
        self.assertEqual(new_tree, expected)

    def test_removal(self):
        tree = AndOperation(
            OrOperation(Word("spam"), Word("ham")),
            AndOperation(Word("foo"), Phrase('"bar"')),
            AndOperation(Phrase('"baz"'), Phrase('"biz"')),
        )

        transformer = self.BasicTransformer()
        new_tree = transformer.visit(tree)

        self.assertEqual(
            new_tree,
            AndOperation(OrOperation(Word("lol"), Word("lol")), Word("lol")),
        )

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

        self.assertEqual(new_tree, AndOperation(Word("lol"), Word("lol")))

    def test_repeating_expression(self):
        # non regression test
        tree = AndOperation(
            Group(OrOperation(Word('bar'), Word('foo'))),
            Group(OrOperation(Word('bar'), Word('foo'), Word('spam'))),
        )
        # basic transformer should not change tree
        same_tree = TreeTransformer().visit(copy.deepcopy(tree))
        self.assertEqual(same_tree, tree)

    def test_more_than_one_element_raises(self):
        tree = Word("foo")
        with self.assertRaises(ValueError) as raised:
            self.RaisingTreeTransformer().visit(tree)
        self.assertIn(
            "The visit of the tree should have produced exactly one element",
            str(raised.exception),
        )

    def test_value_error_pass_through(self):
        # raising a value error that is not related to unpacking passed through
        tree = Word("foo")
        with self.assertRaises(ValueError) as raised:
            self.RaisingTreeTransformer2().visit(tree)
        self.assertEqual("Random error", str(raised.exception))


class PathTrackingVisitorTestCase(TestCase):

    class TermPathVisitor(PathTrackingVisitor):

        def visit_term(self, node, context):
            yield (context["path"], node.value)

    @classmethod
    def setUpClass(cls):
        cls.visit = cls.TermPathVisitor().visit

    def test_visit_simple_term(self):
        paths = self.visit(Word("foo"))
        self.assertEqual(paths, [((), "foo")])

    def test_visit_complex(self):
        tree = AndOperation(
            Group(OrOperation(Word("foo"), Word("bar"), Boost(Fuzzy(Word("baz")), force=2))),
            Proximity(Phrase('"spam ham"')),
            SearchField("fizz", Regex("/fuzz/")),
        )
        paths = self.visit(tree)
        self.assertEqual(
            sorted(paths),
            [
                ((0, 0, 0), "foo"),
                ((0, 0, 1), "bar"),
                ((0, 0, 2, 0, 0), "baz"),
                ((1, 0), '"spam ham"'),
                ((2, 0), '/fuzz/'),
            ]
        )


class PathTrackingTransformerTestCase(TestCase):

    class TermPathTransformer(PathTrackingTransformer):

        def visit_term(self, node, context):
            path = '-'.join(str(i) for i in context['path'])
            quote = '"' if isinstance(node, Phrase) else "/" if isinstance(node, Regex) else ""
            value = node.value.strip(quote)
            new_node = node.clone_item(value=f"{quote}{value}@{path}{quote}")
            yield new_node

    @classmethod
    def setUpClass(cls):
        cls.transform = cls.TermPathTransformer().visit

    def test_visit_simple_term(self):
        tree = self.transform(Word("foo"))
        self.assertEqual(tree, Word("foo@"))

    def test_visit_complex(self):
        tree = AndOperation(
            Group(OrOperation(Word("foo"), Word("bar"), Boost(Fuzzy(Word("baz")), force=2))),
            Proximity(Phrase('"spam ham"')),
            SearchField("fizz", Regex("/fuzz/")),
        )
        transformed = self.transform(tree)
        expected = AndOperation(
            Group(OrOperation(
                Word("foo@0-0-0"),
                Word("bar@0-0-1"),
                Boost(Fuzzy(Word("baz@0-0-2-0-0")), force=2),
            )),
            Proximity(Phrase('"spam ham@1-0"')),
            SearchField("fizz", Regex("/fuzz@2-0/")),
        )
        self.assertEqual(transformed, expected)
