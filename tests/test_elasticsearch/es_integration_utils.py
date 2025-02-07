import json
import os

import elasticsearch_dsl
from elasticsearch.exceptions import ConnectionError
from elasticsearch.helpers import bulk
from elasticsearch_dsl import Date, Index, Integer, Nested, Object, Search, analyzer
from elasticsearch_dsl.connections import connections

from luqum.elasticsearch import ElasticsearchQueryBuilder, SchemaAnalyzer


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
    """Return an es connection or None if none seems available.

    Also wait for ES to be ready (yellow status)
    """
    # you may use ES_HOST environment variable to configure Elasticsearch
    # launching something like
    # docker run --rm -p "127.0.0.1:9200:9200" -e "discovery.type=single-node" elasticsearch:7.8.0
    # is a simple way to get an instance
    connections.configure(
        default=dict(hosts=os.environ.get("ES_HOST", "http://localhost:9200"), timeout=20)
    )
    try:
        client = connections.get_connection("default")
        # check ES running
        client.cluster.health(wait_for_status='yellow')
    except ConnectionError:
        client = None
    return client


if MAJOR_ES > 2:

    class Illustrator(InnerDoc):
        """Inner object to be nested in Book, details on an illustrator
        """
        name = Text()
        birthdate = Date()
        nationality = Keyword()


class Book(Document):
    """An objects representing a book in ES
    """
    title = Text(fields={
        "no_vowels": Text(
            analyzer=analyzer("no_vowels", "pattern", pattern=r"[\Waeiouy]"),  # noqa: W605
            search_analyzer="standard"
        )
    })
    ref = Keyword() if MAJOR_ES > 2 else Text(index="not_analyzed")
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
                "nationality": Keyword() if MAJOR_ES > 2 else Text(index="not_analyzed"),
            }
        )

        class Meta:
            index = "bk"


def add_book_data(es):
    """Create a "bk" index and fill it with data
    """
    remove_book_index(es)
    Book.init()
    with open(os.path.join(os.path.dirname(__file__), "book.json")) as f:
        datas = json.load(f)
    actions = (
        {"_op_type": "index", "_id": i, "_source": d}
        for i, d in enumerate(datas["books"])
    )
    if MAJOR_ES >= 7:
        bulk(es, actions, index="bk", refresh=True)
    else:
        if ES6:
            doc_type = "doc"
        else:
            doc_type = "book"
        bulk(es, actions, index="bk", doc_type=doc_type, refresh=True)


def book_search(es):
    """Return an elasticsearch_dsl search object
    """
    return Search(using=es, index="bk")


def book_query_builder(es):
    """Return an ElasticsearchQueryBuilder adapted for search in book.

    title is adapted to search the title.no_wowels field along with the title
    """
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
    return ElasticsearchQueryBuilder(**builder_options)


def remove_book_index(es):
    """clean "bk" index
    """
    if es is None:
        return
    if ES6:
        Book._index.delete(ignore=404)
    else:
        Index("bk").delete(ignore=404)
