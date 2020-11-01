from unittest import TestCase

from luqum.elasticsearch.nested import extract_nested_queries


class NestedQueriesTestCase(TestCase):

    def test_no_nested(self):
        queries = extract_nested_queries({"term": {"text": {"value": "spam", "_name": "spam"}}})
        self.assertEqual(queries, [])

        queries = extract_nested_queries(
            {"bool": {"must": [
                {"term": {"text": {"value": "spam", "_name": "spam"}}},
                {"term": {"text": {"value": "ham", "_name": "ham"}}},
            ]}}
        )
        self.assertEqual(queries, [])

    def test_nested_no_bool_inside(self):
        queries = extract_nested_queries(
            {"nested": {
                "path": "my",
                "query": {"term": {"text": {"value": "spam", "_name": "spam"}}}
            }}
        )
        self.assertEqual(queries, [])

    def test_nested_bool_inside(self):
        term1 = {"term": {"text": {"value": "spam", "_name": "spam"}}}
        term2 = {"term": {"text": {"value": "ham", "_name": "ham"}}}
        bool_query = {"bool": {"must": [term1, term2]}}
        queries = extract_nested_queries({"nested": {"path": "my", "query": bool_query}})
        self.assertEqual(
            queries,
            [
                {"nested": {"path": "my", "query": term1, "_name": "spam"}},
                {"nested": {"path": "my", "query": term2, "_name": "ham"}},
            ],
        )

    def test_nested_in_bool_with_bool_inside(self):
        term1 = {"term": {"text": {"value": "spam", "_name": "spam"}}}
        term2 = {"term": {"text": {"value": "ham", "_name": "ham"}}}
        term3 = {"term": {"text": {"value": "foo", "_name": "foo"}}}
        bool_query = {"bool": {"must": [term1, term2]}}
        queries = extract_nested_queries(
            {"bool": {"should": [term3, {"nested": {"path": "my", "query": bool_query}}]}}
        )
        self.assertEqual(
            queries,
            [
                {"nested": {"path": "my", "query": term1, "_name": "spam"}},
                {"nested": {"path": "my", "query": term2, "_name": "ham"}},
            ],
        )

    def test_nested_bool_inside_bool(self):
        term1 = {"term": {"text": {"value": "bar", "_name": "bar"}}}
        term2 = {"term": {"text": {"value": "baz", "_name": "baz"}}}
        term3 = {"term": {"text": {"value": "spam", "_name": "spam"}}}
        bool_query1 = {"bool": {"should": [term1, term2]}}
        bool_query2 = {"bool": {"must": [term3, bool_query1]}}
        queries = extract_nested_queries({"nested": {"path": "my", "query": bool_query2}})
        self.assertEqual(queries, [
            {"nested": {"path": "my", "query": term3, "_name": "spam"}},
            {"nested": {"path": "my", "query": bool_query1}},
            {"nested": {"path": "my", "query": term1, "_name": "bar"}},
            {"nested": {"path": "my", "query": term2, "_name": "baz"}},
        ])

    def test_nested_inside_nested(self):
        term1 = {"term": {"text": {"value": "bar", "_name": "bar"}}}
        term2 = {"term": {"text": {"value": "baz", "_name": "baz"}}}
        term3 = {"term": {"text": {"value": "spam", "_name": "spam"}}}
        bool_query1 = {"bool": {"should": [term1, term2]}}
        inner_nested = {"nested": {"path": "my.your", "query": bool_query1}}
        bool_query2 = {"bool": {"must": [term3, inner_nested]}}
        queries = extract_nested_queries({"nested": {"path": "my", "query": bool_query2}})
        self.assertEqual(queries, [
            {"nested": {"path": "my", "query": term3, "_name": "spam"}},
            {"nested": {"path": "my", "query": inner_nested}},
            {"nested": {"path": "my", "_name": "bar", "query": {"nested": {
                "path": "my.your", "query": term1,
            }}}},
            {"nested": {"path": "my", "_name": "baz", "query": {"nested": {
                "path": "my.your", "query": term2,
            }}}},
        ])

    def test_nested_inside_nested_with_nested_bool(self):
        term1 = {"term": {"text": {"value": "bar", "_name": "bar"}}}
        term2 = {"term": {"text": {"value": "foo", "_name": "foo"}}}
        term3 = {"term": {"text": {"value": "spam", "_name": "spam"}}}
        bool_query1 = {"bool": {"must_not": [term1]}}
        bool_query2 = {"bool": {"should": [term2, bool_query1]}}
        inner_nested = {"nested": {"path": "my.your", "query": bool_query2}}
        bool_query3 = {"bool": {"must_not": [inner_nested]}}
        bool_query4 = {"bool": {"must": [term3, bool_query3]}}
        queries = extract_nested_queries({"nested": {"path": "my", "query": bool_query4}})
        self.assertEqual(queries, [
            {"nested": {"path": "my", "query": term3, "_name": "spam"}},
            {"nested": {"path": "my", "query": bool_query3}},
            {"nested": {"path": "my", "query": inner_nested}},
            {"nested": {"path": "my", "_name": "foo", "query": {
                "nested": {"path": "my.your", "query": term2}
            }}},
            {"nested": {
                "path": "my", "query": {"nested": {"path": "my.your", "query": bool_query1}},
            }},
            {"nested": {"path": "my", "_name": "bar", "query": {
                "nested": {"path": "my.your", "query": term1}
            }}},
        ])

    def test_multiple_parallel_nested(self):
        term1 = {"term": {"text": {"value": "bar", "_name": "bar"}}}
        term2 = {"term": {"text": {"value": "foo", "_name": "foo"}}}
        term3 = {"term": {"text": {"value": "spam", "_name": "spam"}}}
        bool_query1 = {"bool": {"should": [term1]}}
        bool_query2 = {"bool": {"must_not": [term2]}}
        nested1 = {"nested": {"path": "my.your", "query": bool_query1}}
        nested2 = {"nested": {"path": "my.his", "query": bool_query2}}
        bool_query3 = {"bool": {"should": [nested2, nested1]}}
        bool_query4 = {"bool": {"must": [term3, bool_query3]}}
        queries = extract_nested_queries({"nested": {"path": "my", "query": bool_query4}})
        self.assertEqual(queries, [
            {"nested": {"path": "my", "query": term3, "_name": "spam"}},
            {"nested": {"path": "my", "query": bool_query3}},
            {"nested": {"path": "my", "query": nested2}},
            {"nested": {"path": "my", "query": nested1}},
            {"nested": {"path": "my", "_name": "foo", "query": {
                "nested": {"path": "my.his", "query": term2}
            }}},
            {"nested": {"path": "my", "_name": "bar", "query": {
                "nested": {"path": "my.your", "query": term1}
            }}},
        ])
