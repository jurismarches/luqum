from unittest import TestCase

from luqum.tree import (
    AndOperation, Word, Prohibit, OrOperation, Not, Phrase, SearchField,
    UnknownOperation, Boost, Fuzzy, Proximity, Range, Group, FieldGroup,
    Plus)
from luqum.naming import auto_name, set_name
from luqum.elasticsearch.visitor import ElasticsearchQueryBuilder


class ElasticsearchTreeTransformerTestCase(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.transformer = ElasticsearchQueryBuilder(
            default_field="text",
            not_analyzed_fields=['not_analyzed_field', 'text', 'author.tag'],
            nested_fields={
                'author': ['name', 'tag']
            },
            object_fields=["book.title", "author.rewards.name"],
            sub_fields=["book.title.raw"],
        )

    def test_named_queries_match(self):
        tree = SearchField("spam", Word("bar"))
        set_name(tree, "a")
        result = self.transformer(tree)
        self.assertEqual(
            result,
            {
                "match": {
                    "spam": {
                        "query": "bar",
                        "_name": "a",
                        "zero_terms_query": "none",
                    },
                },
            },
        )

        tree = SearchField("spam", Phrase('"foo bar"'))
        set_name(tree, "a")
        result = self.transformer(tree)
        self.assertEqual(
            result,
            {
                "match_phrase": {
                    "spam": {
                        "query": "foo bar",
                        "_name": "a",
                    },
                },
            },
        )

    def test_named_queries_term(self):
        tree = SearchField("text", Word("bar"))
        set_name(tree, "a")
        result = self.transformer(tree)
        self.assertEqual(
            result,
            {"term": {"text": {"value": "bar", "_name": "a"}}},
        )

        tree = SearchField("text", Phrase('"foo bar"'))
        set_name(tree, "a")
        result = self.transformer(tree)
        self.assertEqual(
            result,
            {"term": {"text": {"value": "foo bar", "_name": "a"}}},
        )

    def test_named_queries_fuzzy(self):
        tree = SearchField("text", Fuzzy(Word('bar')))
        set_name(tree.children[0], "a")
        result = self.transformer(tree)
        self.assertEqual(
            result,
            {"fuzzy": {"text": {"value": "bar", "_name": "a", 'fuzziness': 0.5}}},
        )

    def test_named_queries_proximity(self):
        tree = SearchField("spam", Proximity(Phrase('"foo bar"')))
        set_name(tree.children[0], "a")
        result = self.transformer(tree)
        self.assertEqual(
            result,
            {"match_phrase": {"spam": {"query": "foo bar", "_name": "a", 'slop': 1.0}}},
        )

    def test_named_queries_boost(self):
        tree = SearchField("text", Boost(Phrase('"foo bar"'), force=2))
        set_name(tree.children[0], "a")
        result = self.transformer(tree)
        self.assertEqual(
            result,
            {"term": {"text": {"value": "foo bar", "_name": "a", 'boost': 2.0}}},
        )

    def test_named_queries_or(self):
        tree = OrOperation(SearchField("text", Word("foo")), SearchField("spam", Word("bar")))
        set_name(tree.operands[0], "a")
        set_name(tree.operands[1], "b")
        result = self.transformer(tree)
        self.assertEqual(
            result,
            {'bool': {'should': [
                {'term': {'text': {'_name': 'a', 'value': 'foo'}}},
                {'match': {'spam': {'_name': 'b', 'query': 'bar', 'zero_terms_query': 'none'}}}
            ]}}
        )

    def test_named_queries_and(self):
        tree = AndOperation(SearchField("text", Word("foo")), SearchField("spam", Word("bar")))
        set_name(tree.operands[0], "a")
        set_name(tree.operands[1], "b")
        result = self.transformer(tree)
        self.assertEqual(
            result,
            {'bool': {'must': [
                {'term': {'text': {'_name': 'a', 'value': 'foo'}}},
                {'match': {'spam': {'_name': 'b', 'query': 'bar', 'zero_terms_query': 'all'}}}
            ]}}
        )

    def test_named_queries_unknown(self):
        tree = UnknownOperation(SearchField("text", Word("foo")), SearchField("spam", Word("bar")))
        set_name(tree.operands[0], "a")
        set_name(tree.operands[1], "b")
        result = self.transformer(tree)
        self.assertEqual(
            result,
            {'bool': {'should': [
                {'term': {'text': {'_name': 'a', 'value': 'foo'}}},
                {'match': {'spam': {'_name': 'b', 'query': 'bar', 'zero_terms_query': 'none'}}}
            ]}}
        )

    def test_named_queries_not(self):
        tree = Not(SearchField("text", Word("foo")))
        set_name(tree, "a")
        result = self.transformer(tree)
        self.assertEqual(
            result,
            {'bool': {'must_not': [{'term': {'text': {'_name': 'a', 'value': 'foo'}}}]}}
        )

        tree = Prohibit(SearchField("text", Word("foo")))
        set_name(tree, "a")
        result = self.transformer(tree)
        self.assertEqual(
            result,
            {'bool': {'must_not': [{'term': {'text': {'_name': 'a', 'value': 'foo'}}}]}}
        )

    def test_named_queries_plus(self):
        tree = Plus(SearchField("text", Word("foo")))
        set_name(tree, "a")
        result = self.transformer(tree)
        self.assertEqual(
            result,
            {'bool': {'must': [{'term': {'text': {'_name': 'a', 'value': 'foo'}}}]}}
        )

    def test_named_queries_range(self):
        tree = SearchField("text", Range(Word("x"), Word("z")))
        set_name(tree, "a")
        result = self.transformer(tree)
        self.assertEqual(result, {'range': {'text': {'_name': 'a', 'gte': 'x', 'lte': 'z'}}})

    def test_named_queries_nested(self):
        tree = SearchField("author.name", Word("Monthy"))
        set_name(tree, "a")
        result = self.transformer(tree)
        # name is repeated on query, but it's not a big deal…
        self.assertEqual(
            result,
            {
                'nested': {
                    '_name': 'a',
                    'path': 'author',
                    'query': {'match': {'author.name': {
                        '_name': 'a', 'query': 'Monthy', 'zero_terms_query':'none',
                    }}},
                },
            }
        )

    def test_named_queries_object(self):
        tree = SearchField("book.title", Word("Circus"))
        set_name(tree, "a")
        result = self.transformer(tree)
        # name is repeated on query, but it's not a big deal…
        self.assertEqual(
            result,
            {
                'match': {'book.title': {
                    '_name': 'a', 'query': 'Circus', 'zero_terms_query': 'none'
                }}
            }
        )

    def test_named_queries_group(self):
        tree = SearchField("text", FieldGroup(Word("bar")))
        set_name(tree.children[0], "a")
        result = self.transformer(tree)
        self.assertEqual(result, {"term": {"text": {"value": "bar", "_name": "a"}}},)

        tree = Group(SearchField("text", Word("bar")))
        set_name(tree, "a")
        result = self.transformer(tree)
        self.assertEqual(result, {"term": {"text": {"value": "bar", "_name": "a"}}},)

    def test_named_queries_complex(self):
        tree = (
            AndOperation(
                SearchField("text", Phrase('"foo bar"')),
                Group(
                    OrOperation(
                        Word("bar"),
                        SearchField("spam", Word("baz")),
                    ),
                ),
            )
        )
        and_op = tree
        search_text = and_op.operands[0]
        or_op = and_op.operands[1].children[0]
        bar = or_op.operands[0]
        search_spam = or_op.operands[1]
        set_name(search_text, "foo_bar")
        set_name(bar, "bar")
        set_name(search_spam, "baz")

        expected = {
            'bool': {'must': [
                {'term': {'text': {'_name': 'foo_bar', 'value': 'foo bar'}}},
                {'bool': {'should': [
                    {'term': {'text': {'_name': 'bar', 'value': 'bar'}}},
                    {'match': {'spam': {
                        '_name': 'baz',
                        'query': 'baz',
                        'zero_terms_query': 'none'
                    }}}
                ]}}
            ]}
        }

        result = self.transformer(tree)
        self.assertEqual(result, expected)

    def test_auto_name_integration(self):
        tree = (
            AndOperation(
                SearchField("text", Phrase('"foo bar"')),
                Group(
                    OrOperation(
                        Word("bar"),
                        SearchField("spam", Word("baz")),
                    ),
                ),
            )
        )
        auto_name(tree)

        expected = {
            'bool': {'must': [
                {'term': {'text': {'_name': 'a', 'value': 'foo bar'}}},
                {'bool': {'should': [
                    {'term': {'text': {'_name': 'c', 'value': 'bar'}}},
                    {'match': {'spam': {
                        '_name': 'd',
                        'query': 'baz',
                        'zero_terms_query': 'none'
                    }}}
                ]}}
            ]}
        }

        result = self.transformer(tree)
        self.assertEqual(result, expected)
