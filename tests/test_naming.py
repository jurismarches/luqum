# -*- coding: utf-8 -*-
from unittest import TestCase

from luqum.naming import (
    auto_name, element_from_name, element_from_path, ExpressionMarker, get_name,
    HTMLMarker, matching_from_names, MatchingPropagator, set_name,
)
from luqum.parser import parser
from luqum.tree import (
    AndOperation, OrOperation, UnknownOperation, SearchField,
    Fuzzy, Proximity, Word, Phrase, Range, Regex, Group, FieldGroup,
    Plus, Not, Prohibit, Boost, Term,
)


def names_to_path(node, path=()):
    names = {}
    node_name = get_name(node)
    if node_name:
        names[node_name] = path
    for i, child in enumerate(node.children):
        names.update(names_to_path(child, path=path + (i,)))
    return names


def simple_naming(node, names=None, path=()):
    """utility to name a big tree, using the node class name or its content if it's a term

    If a name is repeated, it will add numbers. For example : `"or", "or2", "or3, …`.

    return dict: mapping names to path
    """
    if names is None:
        names = {}
    if isinstance(node, (Term)):
        node_name = node.value.strip('"').strip("/").lower()
    else:
        node_name = type(node).__name__.lower()
        if node_name.endswith("operation"):
            node_name = node_name[:-9]
    if node_name in names:
        node_name += str(1 + sum(1 for n in names if n.startswith(node_name)))
    set_name(node, node_name)
    names[node_name] = path
    for i, child in enumerate(node.children):
        simple_naming(child, names, path=path + (i,))
    return names


def paths_to_names(tree, paths):
    return {get_name(element_from_path(tree, path)) for path in paths}


class AutoNameTestCase(TestCase):

    def test_auto_name_one_term(self):
        tree = Word("test")
        names = auto_name(tree)
        self.assertEqual(get_name(tree), "a")
        self.assertEqual(names, {"a": ()})

        tree = Phrase('"test"')
        names = auto_name(tree)
        self.assertEqual(get_name(tree), "a")
        self.assertEqual(names, {"a": ()})

        tree = Range(Word("test"), Word("*"))
        names = auto_name(tree)
        self.assertEqual(get_name(tree), "a")
        self.assertEqual(names, {"a": ()})

        tree = Regex("/test/")
        names = auto_name(tree)
        self.assertEqual(get_name(tree), "a")
        self.assertEqual(names, {"a": ()})

    def test_auto_name_simple_op(self):
        for OpCls in AndOperation, OrOperation, UnknownOperation:
            with self.subTest("operation %r" % OpCls):
                tree = OpCls(
                    Word("test"),
                    Phrase('"test"'),
                )
                names = auto_name(tree)
                self.assertEqual(get_name(tree), None)
                self.assertEqual(get_name(tree.children[0]), "a")
                self.assertEqual(get_name(tree.children[1]), "b")
                self.assertEqual(names, {"a": (0,), "b": (1,)})

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
        names = auto_name(tree)
        self.assertEqual(sorted(names.keys()), list("abcdefgh"))
        # and
        and1 = tree
        self.assertEqual(get_name(and1), None)
        # - or
        or1 = and1.children[0]
        self.assertEqual(get_name(or1), "a")
        self.assertEqual(names["a"], (0,))
        # -- search field
        sfield1 = or1.children[0]
        self.assertEqual(get_name(sfield1), "c")
        self.assertEqual(names["c"], (0, 0))
        self.assertEqual(get_name(sfield1.expr), None)
        # -- and
        and2 = or1.children[1]
        self.assertEqual(get_name(and2), "d")
        self.assertEqual(names["d"], (0, 1))
        # --- proximity phrase
        self.assertEqual(get_name(and2.children[0]), "e")
        self.assertEqual(names["e"], (0, 1, 0))
        self.assertEqual(get_name(and2.children[0].term), None)
        # --- search field
        sfield2 = and2.children[1]
        self.assertEqual(get_name(sfield2), "f")
        self.assertEqual(names["f"], (0, 1, 1))
        self.assertEqual(get_name(sfield2.expr), None)
        # - group
        group1 = and1.children[1]
        self.assertEqual(get_name(group1), "b")
        self.assertEqual(names["b"], (1,))
        # -- unknown op
        unknownop1 = group1.children[0]
        self.assertEqual(get_name(unknownop1), None)
        # --- fuzzy word
        self.assertEqual(get_name(unknownop1.children[0]), "g")
        self.assertEqual(names["g"], (1, 0, 0))
        self.assertEqual(get_name(unknownop1.children[0].term), None)
        # --- phrase
        self.assertEqual(get_name(unknownop1.children[1]), "h")
        self.assertEqual(names["h"], (1, 0, 1))


class UtilitiesTestCase(TestCase):

    def test_matching_from_name(self):
        names = {"a": (0,), "b": (1,), "c": (0, 0), "d": (0, 1), "e": (1, 0, 1)}
        self.assertEqual(
            matching_from_names([], names), (set(), {(0,), (1,), (0, 0), (0, 1), (1, 0, 1)})
        )
        self.assertEqual(
            matching_from_names(["a", "b"], names), ({(0,), (1,)}, {(0, 0), (0, 1), (1, 0, 1)})
        )
        self.assertEqual(
            matching_from_names(["a", "e"], names), ({(0,), (1, 0, 1)}, {(1,), (0, 0), (0, 1)})
        )
        self.assertEqual(
            matching_from_names(["c"], names), ({(0, 0)}, {(0,), (1,), (0, 1), (1, 0, 1)})
        )
        with self.assertRaises(KeyError):
            matching_from_names(["x"], names)

    def test_element_from_path(self):
        tree = AndOperation(
            OrOperation(
                SearchField("bar", Word("test")),
                Group(
                    AndOperation(
                        Proximity(Phrase('"test"'), 2),
                        SearchField("baz", Word("test")),
                        Fuzzy(Word("test")),
                        Phrase('"test"'),
                    ),
                ),
            ),
        )
        names = {"a": (), "b": (0, 1), "c": (0, 1, 0, 2), "d": (0, 1, 0, 2, 0), "e": (0, 1, 0, 3)}
        self.assertEqual(element_from_path(tree, ()), tree)
        self.assertEqual(element_from_name(tree, "a", names), tree)
        self.assertEqual(element_from_path(tree, (0, 1)), tree.children[0].children[1])
        self.assertEqual(element_from_name(tree, "b", names), tree.children[0].children[1])
        self.assertEqual(element_from_path(tree, (0, 1, 0, 2)), Fuzzy(Word("test")))
        self.assertEqual(element_from_name(tree, "c", names), Fuzzy(Word("test")))
        self.assertEqual(element_from_path(tree, (0, 1, 0, 2, 0)), Word("test"))
        self.assertEqual(element_from_name(tree, "d", names), Word("test"))
        self.assertEqual(element_from_path(tree, (0, 1, 0, 3)), Phrase('"test"'))
        self.assertEqual(element_from_name(tree, "e", names), Phrase('"test"'))
        with self.assertRaises(IndexError):
            element_from_path(tree, (1,))


class PropagateMatchingTestCase(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.propagate_matching = MatchingPropagator()

    def test_or_operation(self):
        tree = OrOperation(Word("foo"), Phrase('"bar"'), Word("baz"))
        all_paths = {(0,), (1,), (2,)}

        matching = set()
        paths_ok, paths_ko = self.propagate_matching(tree, matching, all_paths - matching)
        self.assertEqual(paths_ok, set())
        self.assertEqual(paths_ko, {(), (0,), (1,), (2,), })

        matching = {(2, )}
        paths_ok, paths_ko = self.propagate_matching(tree, matching, all_paths - matching)
        self.assertEqual(paths_ok, {(), (2, )})
        self.assertEqual(paths_ko, {(0,), (1,)})

        matching = {(0, ), (2, )}
        paths_ok, paths_ko = self.propagate_matching(tree, matching, all_paths - matching)
        self.assertEqual(paths_ok, {(), (0, ), (2,)})
        self.assertEqual(paths_ko, {(1,)})

        matching = {(0, ), (1, ), (2, )}
        paths_ok, paths_ko = self.propagate_matching(tree, matching, all_paths - matching)
        self.assertEqual(paths_ok, {(), (0,), (1,), (2, )})
        self.assertEqual(paths_ko, set())

    def test_and_operation(self):
        tree = AndOperation(Word("foo"), Phrase('"bar"'), Word("baz"))
        all_paths = {(0,), (1,), (2,)}

        matching = set()
        paths_ok, paths_ko = self.propagate_matching(tree, matching, all_paths - matching)
        self.assertEqual(paths_ok, set())
        self.assertEqual(paths_ko, {(), (0,), (1,), (2,), })

        matching = {(2, )}
        paths_ok, paths_ko = self.propagate_matching(tree, matching, all_paths - matching)
        self.assertEqual(paths_ok, {(2, )})
        self.assertEqual(paths_ko, {(), (0,), (1,)})

        matching = {(0, ), (2, )}
        paths_ok, paths_ko = self.propagate_matching(tree, matching, all_paths - matching)
        self.assertEqual(paths_ok, {(0, ), (2,)})
        self.assertEqual(paths_ko, {(), (1,)})

        matching = {(0, ), (1, ), (2, )}
        paths_ok, paths_ko = self.propagate_matching(tree, matching, all_paths - matching)
        self.assertEqual(paths_ok, {(), (0,), (1,), (2, )})
        self.assertEqual(paths_ko, set())

    def test_unknown_operation(self):
        tree = UnknownOperation(Word("foo"), Phrase('"bar"'), Word("baz"))

        tree_or = OrOperation(Word("foo"), Phrase('"bar"'), Word("baz"))
        tree_and = AndOperation(Word("foo"), Phrase('"bar"'), Word("baz"))
        propagate_or = self.propagate_matching
        propagate_and = MatchingPropagator(default_operation=AndOperation)
        all_paths = {(0,), (1,), (2,)}

        for matching in [set(), {(2, )}, {(0, ), (2, )}, {(0, ), (1, ), (2, )}]:
            self.assertEqual(
                propagate_or(tree, matching),
                self.propagate_matching(tree_or, matching, matching - all_paths),
            )
            self.assertEqual(
                propagate_and(tree, matching),
                self.propagate_matching(tree_and, matching, matching - all_paths),
            )

    def test_negation(self):
        for tree in [Prohibit(Word("foo")), Not(Word("foo"))]:
            with self.subTest("%r" % type(tree)):
                paths_ok, paths_ko = self.propagate_matching(tree, set(), {(0, )})
                self.assertEqual(paths_ok, {()})
                self.assertEqual(paths_ko, {(0,)})

                paths_ok, paths_ko = self.propagate_matching(tree, {(0, )}, set())
                self.assertEqual(paths_ok, {(0,)})
                self.assertEqual(paths_ko, {()})

    def test_nested_negation(self):
        for NegClass in (Prohibit, Not):
            with self.subTest("%r" % NegClass):
                tree = AndOperation(
                    NegClass(OrOperation(
                        NegClass(AndOperation(
                            NegClass(Word("a")),
                            Word("b"),
                        )),
                        Word("c"),
                    )),
                    Word("d"),
                )
                a, b, c, d = (0, 0, 0, 0, 0, 0), (0, 0, 0, 0, 1), (0, 0, 1), (1,)
                not_a, ab, not_ab = (0, 0, 0, 0, 0), (0, 0, 0, 0), (0, 0, 0)
                abc, not_abc, abcd = (0, 0), (0,), ()

                paths_ok, paths_ko = self.propagate_matching(tree, set(), {a, b, c, d})
                self.assertEqual(paths_ok, {not_a, not_ab, abc})
                self.assertEqual(paths_ko, {a, b, ab, c, not_abc, d, abcd})

                paths_ok, paths_ko = self.propagate_matching(tree, {b, d}, {a, c})
                self.assertEqual(paths_ok, {not_a, b, ab, not_abc, d, abcd})
                self.assertEqual(paths_ko, {a, not_ab, c, abc})

                paths_ok, paths_ko = self.propagate_matching(tree, {a, b, c}, {d})
                self.assertEqual(paths_ok, {a, b, not_ab, c, abc})
                self.assertEqual(paths_ko, {not_a, ab, not_abc, d, abcd})

                paths_ok, paths_ko = self.propagate_matching(tree, {a, b, c, d}, set())
                self.assertEqual(paths_ok, {a, b, not_ab, c, abc, d})
                self.assertEqual(paths_ko, {not_a, ab, not_abc, abcd})

    def test_single_element(self):
        for tree in [Word("a"), Phrase('"a"'), Regex("/a/")]:
            with self.subTest("%r" % type(tree)):
                paths_ok, paths_ko = self.propagate_matching(tree, set())
                self.assertEqual(paths_ok, set(), {()})
                self.assertEqual(paths_ko, {()})

                paths_ok, paths_ko = self.propagate_matching(tree, {()})
                self.assertEqual(paths_ok, {()}, set())
                self.assertEqual(paths_ko, set())

    def test_no_propagation(self):
        for tree in [Range(Word("a"), Word("b")), Fuzzy(Word("foo")), Proximity('"bar baz"', 2)]:
            with self.subTest("%r" % type(tree)):
                paths_ok, paths_ko = self.propagate_matching(tree, set(), {()})

                # no down propagation
                self.assertEqual(paths_ok, set())
                self.assertEqual(paths_ko, {()})

                paths_ok, paths_ko = self.propagate_matching(tree, {()}, set())
                self.assertEqual(paths_ok, {()})
                self.assertEqual(paths_ko, set())

    def test_simple_propagation(self):
        # propagation in nodes with only one children
        tree = Boost(Group(SearchField("foo", FieldGroup(Plus(Word("bar"))))), force=2)

        paths_ok, paths_ko = self.propagate_matching(tree, set(), {()})
        self.assertEqual(paths_ok, set())
        self.assertEqual(paths_ko, {(), (0,), (0, 0), (0, 0, 0), (0, 0, 0, 0), (0, 0, 0, 0, 0)})

        paths_ok, paths_ko = self.propagate_matching(tree, {()}, set())
        self.assertEqual(paths_ok, {(), (0,), (0, 0), (0, 0, 0), (0, 0, 0, 0), (0, 0, 0, 0, 0)})
        self.assertEqual(paths_ko, set())

    def test_combination(self):
        tree = AndOperation(
            OrOperation(
                SearchField(
                    "mine",
                    FieldGroup(
                        Plus(
                            AndOperation(
                                Word("foo"),
                                Regex("/fizz/"),
                            ),
                        ),
                    ),
                ),
                Boost(
                    Group(
                        AndOperation(
                            Phrase('"ham"'),
                            Word("spam"),
                            Prohibit(Fuzzy(Word("fuzz"))),
                        ),
                    ),
                    force=2,
                ),
            ),
            Not(
                OrOperation(
                    Word('"bar"'),
                    Word('"baz"'),
                ),
            ),
        )
        to_path = simple_naming(tree)

        paths_ok, paths_ko = self.propagate_matching(tree, set())
        self.assertEqual(
            paths_to_names(tree, paths_ok),
            {"prohibit", "not"},
        )
        self.assertEqual(
            paths_to_names(tree, paths_ko),
            {
                "and", "or", "searchfield", "fieldgroup", "plus", "and2", "foo", "fizz",
                "boost", "group", "and3", "ham", "spam", "fuzzy", "or2", "bar", "baz"
            },
        )

        # adding matching just enough positive expressions, so that complete expression matches
        paths_ok, paths_ko = self.propagate_matching(
            tree, {to_path["foo"], to_path["fizz"], to_path["ham"]},
        )
        self.assertEqual(
            paths_to_names(tree, paths_ok),
            {
                "and", "or", "searchfield", "fieldgroup", "plus", "and2", "foo", "fizz", "ham",
                "prohibit", "not"
            },
        )
        self.assertEqual(
            paths_to_names(tree, paths_ko),
            {"boost", "group", "and3", "spam", "fuzzy", "or2", "bar", "baz"},
        )

        # making everything match
        paths_ok, paths_ko = self.propagate_matching(
            tree, {to_path["foo"], to_path["fizz"], to_path["ham"], to_path["spam"]},
        )
        self.assertEqual(
            paths_to_names(tree, paths_ok),
            {"and", "or", "searchfield", "fieldgroup", "plus", "and2", "foo", "fizz", "ham",
             "prohibit", "boost", "group", "and3", "spam", "not"}
        )
        self.assertEqual(paths_to_names(tree, paths_ko), {"fuzzy", "or2", "bar", "baz"})

        # making everything match, but some negative expression
        paths_ok, paths_ko = self.propagate_matching(
            tree,
            {
                to_path["foo"], to_path["fizz"], to_path["ham"], to_path["spam"],
                to_path["fuzzy"], to_path["bar"],
            },
        )
        self.assertEqual(
            paths_to_names(tree, paths_ok),
            {
                "or", "searchfield", "fieldgroup", "plus", "and2",
                "foo", "fizz", "ham", "spam", "fuzzy", "or2", "bar",
            },
        )
        self.assertEqual(
            paths_to_names(tree, paths_ko),
            {
                "and", "boost", "group", "and3", "prohibit",
                "boost", "group", "and3", "not", "baz",
            },
        )


class HTMLMarkerTestCase(TestCase):

    mark_html = HTMLMarker()

    def test_single_element(self):
        ltree = parser.parse('"b"')
        out = self.mark_html(ltree, {()}, set())
        self.assertEqual(out, '<span class="ok">"b"</span>')
        out = self.mark_html(ltree, {()}, set(), parcimonious=False)
        self.assertEqual(out, '<span class="ok">"b"</span>')
        out = self.mark_html(ltree, set(), {()})
        self.assertEqual(out, '<span class="ko">"b"</span>')
        out = self.mark_html(ltree, set(), {()}, parcimonious=False)
        self.assertEqual(out, '<span class="ko">"b"</span>')

    def test_multiple_elements(self):
        ltree = parser.parse('(foo OR bar~2 OR baz^2) AND NOT spam')

        names = simple_naming(ltree)
        foo, bar, baz, spam = names["foo"], names["fuzzy"], names["boost"], names["spam"]
        or_, and_, not_ = names["or"], names["and"], names["not"]

        out = self.mark_html(ltree, {foo, bar, baz, or_, and_, not_}, {spam})
        self.assertEqual(
            out,
            '<span class="ok">(foo OR bar~2 OR baz^2) AND NOT<span class="ko"> spam</span></span>',
        )
        out = self.mark_html(ltree, {foo, bar, baz, or_, and_, not_}, {spam}, parcimonious=False)
        self.assertEqual(
            out,
            '<span class="ok">'
            '(<span class="ok"><span class="ok">foo </span>OR<span class="ok"> bar~2 </span>OR'
            '<span class="ok"> baz^2</span></span>) '
            'AND'
            '<span class="ok"> NOT<span class="ko"> spam</span></span>'
            '</span>',
        )

        out = self.mark_html(ltree, {not_}, {foo, bar, baz, or_, and_, spam})
        self.assertEqual(
            out,
            '<span class="ko">(foo OR bar~2 OR baz^2) AND'
            '<span class="ok"> NOT<span class="ko"> spam</span></span></span>',
        )

        # changing class name and element name
        mark = HTMLMarker(ok_class="success", ko_class="failure", element="li")
        out = mark(ltree, {not_}, {foo, bar, baz, or_, and_, spam})
        self.assertEqual(
            out,
            '<li class="failure">(foo OR bar~2 OR baz^2) AND'
            '<li class="success"> NOT<li class="failure"> spam</li></li></li>',
        )

    def test_expression_marker(self):
        # only for coverage !
        ltree = parser.parse("foo AND bar")
        mark = ExpressionMarker()
        out = mark(ltree, {(), (0,), (1,)}, {})
        self.assertEqual(out, ltree)
