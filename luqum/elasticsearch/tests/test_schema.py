from unittest import TestCase

from ..schema import SchemaAnalyzer


class SchemaAnalyzerTestCase(TestCase):

    INDEX_SETTINGS = {
        "settings": {
            "query": {"default_field": "text"},
        },
        "mappings": {
            "type1": {
                "properties": {
                    "text": {"type": "text"},
                    "author": {
                        "type": "nested",
                        "properties": {
                            "firstname": {
                                "type": "text",
                                "fields": {
                                    # sub fields
                                    "english": {"analyzer": "english"},
                                    "raw": {"type": "keyword"},
                                }
                            },
                            "lastname": {"type": "text"},
                            "book": {
                                "type": "nested",
                                "properties": {
                                    "title": {"type": "text"},
                                    "isbn": {  # an object field in deep nested field
                                        "type": "object",
                                        "properties": {
                                            "ref": {
                                                "type": "keyword",
                                            },
                                        },
                                    },
                                    "format": {
                                        "type": "nested",
                                        "properties": {
                                            "ftype": {"type": "keyword"},
                                        },
                                    },
                                },
                            },
                        },
                    },
                    "publish": {
                        "type": "nested",
                        "properties": {
                            "site": {"type": "keyword"},
                            "idnum": {"type": "long"},
                        },
                    },
                    "manager": {
                        "type": "object",
                        "properties": {
                            "firstname": {"type": "text"},
                            "address": {  # an object field in an object field
                                "type": "object",
                                "properties": {
                                    "zipcode": {"type": "keyword"},
                                },
                            },
                            "subteams": {  # a nested in an object field
                                "type": "nested",
                                "properties": {
                                    "supervisor": {  # with an object field inside
                                        "type": "object",
                                        "properties": {
                                            "name": {
                                                "type": "text",
                                                # sub field
                                                "fields": {"raw": {"type": "keyword"}},
                                            },
                                        },
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
    }

    def test_default_field(self):
        s = SchemaAnalyzer(self.INDEX_SETTINGS)
        self.assertEqual(s.default_field(), "text")

    def test_not_analyzed_fields(self):
        s = SchemaAnalyzer(self.INDEX_SETTINGS)
        self.assertEqual(
            sorted(s.not_analyzed_fields()),
            [
                'author.book.format.ftype',
                'author.book.isbn.ref',
                'author.firstname.raw',
                'manager.address.zipcode',
                'manager.subteams.supervisor.name.raw',
                'publish.idnum',
                'publish.site',
            ],
        )

    def test_nested_fields(self):
        s = SchemaAnalyzer(self.INDEX_SETTINGS)
        self.assertEqual(
            s.nested_fields(),
            {
                'author': {
                    'firstname': {},
                    'lastname': {},
                    'book': {
                        'format': {
                            'ftype': {}
                        },
                        'title': {},
                        'isbn': {},
                    },
                },
                'publish': {
                    'site': {},
                    'idnum': {},
                },
                'manager.subteams': {  # FIXME !!!!
                    'supervisor': {},
                },
            }
        )

    def test_object_fields(self):
        s = SchemaAnalyzer(self.INDEX_SETTINGS)
        self.assertEqual(
            sorted(s.object_fields()),
            [
                'author.book.isbn.ref',
                'manager.address.zipcode',
                'manager.firstname',
                'manager.subteams.supervisor.name',
            ]
        )

    def test_sub_fields(self):
        s = SchemaAnalyzer(self.INDEX_SETTINGS)
        self.assertEqual(
            sorted(s.sub_fields()),
            [
                'author.firstname.english',
                'author.firstname.raw',
                'manager.subteams.supervisor.name.raw',
            ]
        )

    def test_empty(self):
        s = SchemaAnalyzer({})
        self.assertEqual(s.default_field(), "*")
        self.assertEqual(list(s.not_analyzed_fields()), [])
        self.assertEqual(s.nested_fields(), {})
        self.assertEqual(list(s.object_fields()), [])
