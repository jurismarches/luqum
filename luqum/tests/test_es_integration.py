import json
from unittest import TestCase, skipIf

import elasticsearch_dsl
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import ConnectionError
from elasticsearch.helpers import bulk
from elasticsearch_dsl import Date, Index, Integer, Nested, Object, Search, analyzer
from elasticsearch_dsl.connections import connections
from luqum.elasticsearch import ElasticsearchQueryBuilder, SchemaAnalyzer
from luqum.parser import parser

MAJOR_ES = elasticsearch_dsl.VERSION[0]
if MAJOR_ES > 2:
    from elasticsearch_dsl import Keyword

ES6 = False
if MAJOR_ES >= 6:
    from elasticsearch_dsl import Text, Document, InnerDoc

    ES6 = True
else:
    from elasticsearch_dsl import (
        String as Text,
        DocType as Document,
        InnerObjectWrapper as InnerDoc,
    )


def get_es():
    connections.create_connection(hosts=["localhost"], timeout=20)
    client = Elasticsearch()
    try:
        # check ES runnig
        client.cluster.health(wait_for_status='yellow')
    except ConnectionError:
        client = None
    return client


if MAJOR_ES > 2:

    class Illustrator(InnerDoc):
        name = Text()
        birthdate = Date()
        nationality = Keyword()


class Book(Document):
    title = Text(fields={
        "no_vowels": Text(
            analyzer=analyzer("no_vowels", "pattern", pattern="[\Waeiouy]"),  # noqa: W605
            search_analyzer="standard"
        )
    })
    edition = Text()
    author = Object(properties={"name": Text(), "birthdate": Date()})
    publication_date = Date()
    n_pages = Integer()

    if ES6:
        illustrators = Nested(Illustrator)

        class Index:
            name = "bk"

    else:
        illustrators = Nested(
            properties={
                "name": Text(),
                "birthdate": Date(),
                "nationality": Keyword()
                if MAJOR_ES > 2
                else Text(index="not_analyzed"),
            }
        )

        class Meta:
            index = "bk"


def add_data():
    search = connections.get_connection()
    Book.init()
    with open("luqum/tests/book.json") as f:
        datas = json.load(f)

    actions = (
        {"_op_type": "index", "_id": i, "_source": d}
        for i, d in enumerate(datas["books"])
    )
    if MAJOR_ES >= 7:
        bulk(search, actions, index="bk", refresh=True)
    else:
        if ES6:
            doc_type = "doc"
        else:
            doc_type = "book"

        bulk(search, actions, index="bk", doc_type=doc_type, refresh=True)


@skipIf(get_es() is None, "Skipping ES test as I can't reach ES")
class LuqumRequestTestCase(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.es_client = get_es()
        if cls.es_client is None:
            return
        cls.search = Search(using=cls.es_client, index="bk")
        MESSAGES_SCHEMA = {"mappings": Book._doc_type.mapping.to_dict()}
        schema_analizer = SchemaAnalyzer(MESSAGES_SCHEMA)

        builder_options = schema_analizer.query_builder_options()
        builder_options['field_options'] = {
            'title.no_vowels': {
                'match_type': 'multi_match',
                'type': 'most_fields',
                'fields': ('title', 'title.no_vowels')
            }
        }
        cls.es_builder = ElasticsearchQueryBuilder(**builder_options)
        add_data()

    def _ask_luqum(self, req):
        tree = parser.parse(req)
        query = self.es_builder(tree)
        return [x.title for x in self.search.filter(query).execute()]

    def test_simple_field_search(self):
        self.assertListEqual(
            self._ask_luqum('title:"Chamber"'),
            ["Harry Potter and the Chamber of Secrets"],
        )

    def test_nested_field_search(self):
        self.assertListEqual(
            self._ask_luqum("illustrators:(name:Giles)"),
            ["Harry Potter and the Goblet of Fire"],
        )

    def test_or_condition_search(self):
        self.assertCountEqual(
            self._ask_luqum(
                'illustrators:(name:"Giles Greenfield" OR name:"Cliff Wright")'
            ),
            [
                "Harry Potter and the Prisoner of Azkaban",
                "Harry Potter and the Chamber of Secrets",
                "Harry Potter and the Goblet of Fire",
            ],
        )

    def test_and_condition_search(self):
        self.assertCountEqual(
            self._ask_luqum(
                'illustrators:(name:"Cliff Wright") AND illustrators:(name:"Mary GrandPré")'
            ),
            [
                "Harry Potter and the Prisoner of Azkaban",
                "Harry Potter and the Chamber of Secrets",
            ],
        )

    def test_date_range_search(self):
        self.assertCountEqual(
            self._ask_luqum("publication_date:[2005-01-01 TO 2010-12-31]"),
            [
                "Harry Potter and the Half-Blood Prince",
                "The Tales of Beedle the Bard",
                "Harry Potter and the Deathly Hallows",
            ],
        )

    def test_int_range_search(self):
        self.assertCountEqual(
            self._ask_luqum("n_pages:[500 TO *]"),
            [
                "Harry Potter and the Half-Blood Prince",
                "Harry Potter and the Order of the Phoenix",
                "Harry Potter and the Deathly Hallows",
                "Harry Potter and the Goblet of Fire",
            ],
        )

    def test_int_search(self):
        self.assertListEqual(
            self._ask_luqum("n_pages:360"), ["Harry Potter and the Cursed Child"]
        )

    def test_proximity_search(self):
        self.assertListEqual(
            self._ask_luqum('title:"Harry Secrets"~5'),
            ["Harry Potter and the Chamber of Secrets"],
        )

    def test_fuzzy_search(self):
        self.assertListEqual(
            self._ask_luqum("title:Gublet~2"), ["Harry Potter and the Goblet of Fire"]
        )

    def test_object_field_search(self):
        self.assertListEqual(
            self._ask_luqum('illustrators:(name:"J. K. Rowling")'),
            ["The Tales of Beedle the Bard"],
        )

    def test_fail_search(self):
        self.assertListEqual(self._ask_luqum("title:secret"), [])

    def test_wildcard_matching(self):
        self.assertListEqual(
            self._ask_luqum("title:secret*"),
            ["Harry Potter and the Chamber of Secrets"],
        )

    def test_wildcard1_search(self):
        self.assertListEqual(
            self._ask_luqum("title:P*ix"), ["Harry Potter and the Order of the Phoenix"]
        )

    def test_not_search(self):
        self.assertListEqual(
            self._ask_luqum("-title:Harry"), ["The Tales of Beedle the Bard"]
        )

    def test_not_analysed_field_search(self):
        self.assertListEqual(self._ask_luqum("illustrators:nationality:uk"), [])

    def test_complex_search(self):
        self.assertListEqual(
            self._ask_luqum(
                """
                    title:phoenux~2 AND
                    illustrators:name:Grand* AND
                    illustrators:(
                        -name:grandpr* AND (
                            name:J*on OR birthdate:[1950-01-01 TO 1970-01-01]
                        )
                    )
                """
            ),
            ["Harry Potter and the Order of the Phoenix"],
        )

    def test_subfield_multi_match_search(self):
        self.assertListEqual(
            self._ask_luqum("title.no_vowels:Potter AND title.no_vowels:x"),
            ["Harry Potter and the Order of the Phoenix"],
        )

    @classmethod
    def tearDownClass(cls):
        if cls.es_client is None:
            return
        if ES6:
            Book._index.delete()
        else:
            Index("bk").delete(ignore=404)
