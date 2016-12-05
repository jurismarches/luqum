from unittest import TestCase

from luqum.exceptions import OrAndAndOnSameLevel, NestedSearchFieldException
from luqum.parser import parser
from luqum.tree import (
    AndOperation, Word, Prohibit, OrOperation, Not, Phrase, SearchField,
    UnknownOperation, Boost, Fuzzy, Proximity, Range, Group, FieldGroup,
    Plus)
from ..visitor import ElasticsearchQueryBuilder


class ElasticsearchTreeTransformerTestCase(TestCase):

    def setUp(self):
        self.transformer = ElasticsearchQueryBuilder(
            default_field="text",
            not_analyzed_fields=['not_analyzed_field', 'text', 'author.tag'],
            nested_fields={
                'author': ['name', 'tag']
            }
        )

    def test_should_raise_when_nested_search_field(self):
        tree = SearchField(
            'spam',
            OrOperation(Word('egg'), SearchField('monty', Word('python')))
        )
        with self.assertRaises(NestedSearchFieldException):
            self.transformer(tree)

    def test_should_transform_and(self):
        tree = AndOperation(Word('spam'), Word('eggs'))
        result = self.transformer(tree)
        expected = {'bool': {'must': [
            {"term": {"text": {"value": 'spam'}}},
            {"term": {"text": {"value": 'eggs'}}},
        ]}}
        self.assertDictEqual(result, expected)

    def test_should_transform_plus(self):
        tree = Plus(Word("spam"))
        result = self.transformer(tree)
        expected = {'bool': {'must': [
            {"term": {"text": {"value": 'spam'}}},
        ]}}
        self.assertDictEqual(result, expected)

    def test_should_transform_or(self):
        tree = OrOperation(Word('spam'), Word('eggs'))
        result = self.transformer(tree)
        expected = {'bool': {'should': [
            {"term": {"text": {"value": 'spam'}}},
            {"term": {"text": {"value": 'eggs'}}},
        ]}}
        self.assertDictEqual(result, expected)

    def test_should_raise_when_or_and_and_on_same_level(self):
        tree = OrOperation(
            Word('spam'),
            AndOperation(Word('eggs'), Word('monty'))
        )
        with self.assertRaises(OrAndAndOnSameLevel):
            self.transformer(tree)

    def test_should_raise_when_or_and_and_on_same_level2(self):
        tree = UnknownOperation(
            Word('spam'),
            AndOperation(Word('eggs'), Word('monty'))
        )
        with self.assertRaises(OrAndAndOnSameLevel):
            self.transformer(tree)

    def test_should_raise_when_or_and_not_on_same_level(self):
        transformer = ElasticsearchQueryBuilder(
            default_field="text",
            not_analyzed_fields=['not_analyzed_field', 'text'],
            default_operator=ElasticsearchQueryBuilder.MUST
        )
        tree = OrOperation(
            Word('spam'),
            UnknownOperation(Word('test'), Prohibit(Word('eggs')))
        )
        with self.assertRaises(OrAndAndOnSameLevel):
            transformer(tree)

    def test_should_raise_when_or_and_not_on_same_level2(self):
        transformer = ElasticsearchQueryBuilder(
            default_field="text",
            not_analyzed_fields=['not_analyzed_field', 'text'],
            default_operator=ElasticsearchQueryBuilder.MUST
        )
        tree = UnknownOperation(
            Word('spam'),
            OrOperation(Word('test'), Prohibit(Word('eggs')))
        )
        with self.assertRaises(OrAndAndOnSameLevel):
            transformer(tree)

    def test_should_raise_when_or_and_not_on_same_level3(self):
        transformer = ElasticsearchQueryBuilder(
            default_field="text",
            not_analyzed_fields=['not_analyzed_field', 'text'],
            default_operator=ElasticsearchQueryBuilder.MUST
        )
        tree = UnknownOperation(
            Group(Word('preparation*')),
            UnknownOperation(
                Word('CFG'),
                OrOperation(Word('test'), Word('fuck'))
            )
        )

        with self.assertRaises(OrAndAndOnSameLevel):
            transformer(tree)

    def test_should_transform_prohibit(self):
        tree = Prohibit(Word("spam"))
        result = self.transformer(tree)
        expected = {'bool': {'must_not': [
            {"term": {"text": {"value": 'spam'}}},
        ]}}
        self.assertDictEqual(result, expected)

    def test_should_transform_not(self):
        tree = Not(Word('spam'))
        result = self.transformer(tree)
        expected = {'bool': {'must_not': [
            {"term": {"text": {"value": 'spam'}}},
        ]}}
        self.assertDictEqual(result, expected)

    def test_should_transform_word(self):
        tree = Word('spam')
        result = self.transformer(tree)
        expected = {"term": {"text": {"value": 'spam'}}}
        self.assertDictEqual(result, expected)

    def test_should_transform_word_with_custom_search_field(self):
        transformer = ElasticsearchQueryBuilder(
            default_field="custom",
            not_analyzed_fields=['custom']
        )
        tree = Word('spam')
        result = transformer(tree)
        expected = {"term": {"custom": {"value": 'spam'}}}
        self.assertDictEqual(result, expected)

    def test_should_transform_phrase(self):
        tree = Phrase('"spam eggs"')
        result = self.transformer(tree)
        expected = {"match_phrase": {"text": {"query": 'spam eggs'}}}
        self.assertDictEqual(result, expected)

    def test_should_transform_phrase_with_custom_search_field(self):
        transformer = ElasticsearchQueryBuilder(default_field="custom")
        tree = Phrase('"spam eggs"')
        result = transformer(tree)
        expected = {"match_phrase": {"custom": {"query": 'spam eggs'}}}
        self.assertDictEqual(result, expected)

    def test_should_transform_phrase_with_search_field(self):
        tree = SearchField('monthy', Phrase('"spam eggs"'))
        result = self.transformer(tree)
        expected = {"match_phrase": {"monthy": {"query": 'spam eggs'}}}
        self.assertDictEqual(result, expected)

    def test_should_transform_search_field(self):
        tree = SearchField("pays", Word("spam"))
        result = self.transformer(tree)
        expected = {"match": {"pays": {"query": 'spam', 'type': 'phrase', 'zero_terms_query': 'none'}}}
        self.assertDictEqual(result, expected)

    def test_should_transform_unknown_operation_default(self):
        tree = UnknownOperation(Word("spam"), Word("eggs"))
        result = self.transformer(tree)
        expected = {'bool': {'should': [
            {"term": {"text": {"value": 'spam'}}},
            {"term": {"text": {"value": 'eggs'}}},
        ]}}
        self.assertDictEqual(result, expected)

    def test_should_transform_unknown_operation_default_must(self):
        transformer = ElasticsearchQueryBuilder(
            default_operator=ElasticsearchQueryBuilder.MUST,
            not_analyzed_fields=['text']
        )
        tree = UnknownOperation(Word("spam"), Word("eggs"))
        result = transformer(tree)
        expected = {'bool': {'must': [
            {"term": {"text": {"value": 'spam'}}},
            {"term": {"text": {"value": 'eggs'}}},
        ]}}
        self.assertDictEqual(result, expected)

    def test_should_transform_unknown_operation_default_should(self):
        transformer = ElasticsearchQueryBuilder(
            default_operator=ElasticsearchQueryBuilder.SHOULD,
            not_analyzed_fields=['text']
        )
        tree = UnknownOperation(Word("spam"), Word("eggs"))
        result = transformer(tree)
        expected = {'bool': {'should': [
            {"term": {"text": {"value": 'spam'}}},
            {"term": {"text": {"value": 'eggs'}}},
        ]}}
        self.assertDictEqual(result, expected)

    def test_should_simplify_nested_and(self):
        tree = AndOperation(
            Word("spam"),
            AndOperation(
                Word("eggs"),
                AndOperation(
                    Word("monthy"),
                    Word("python")
                )
            )
        )
        result = self.transformer(tree)
        expected = {'bool': {'must': [
            {"term": {"text": {"value": 'spam'}}},
            {"term": {"text": {"value": 'eggs'}}},
            {"term": {"text": {"value": 'monthy'}}},
            {"term": {"text": {"value": 'python'}}},
        ]}}
        self.assertDictEqual(result, expected)

    def test_should_simplify_nested_or(self):
        tree = OrOperation(
            Word("spam"),
            OrOperation(
                Word("eggs"),
                OrOperation(
                    Word("monthy"),
                    Word("python")
                )
            )
        )
        result = self.transformer(tree)
        expected = {'bool': {'should': [
            {"term": {"text": {"value": 'spam'}}},
            {"term": {"text": {"value": 'eggs'}}},
            {"term": {"text": {"value": 'monthy'}}},
            {"term": {"text": {"value": 'python'}}},
        ]}}
        self.assertDictEqual(result, expected)

    def test_should_not_simplify_nested_or_in_and(self):
        tree = AndOperation(
            Word("spam"),
            OrOperation(
                Word("eggs"),
                AndOperation(
                    Word("monthy"),
                    Word("python")
                )
            )
        )

        with self.assertRaises(OrAndAndOnSameLevel):
            self.transformer(tree)

    def test_should_transform_boost_in_word(self):
        tree = Boost(Word("spam"), 1)
        result = self.transformer(tree)
        expected = {"term": {"text": {"value": 'spam', "boost": 1.00}}}
        self.assertDictEqual(result, expected)

    def test_should_transform_wildcard_in_word(self):
        tree = Word("spam*")
        result = self.transformer(tree)
        expected = {"wildcard": {"text": {"value": 'spam*'}}}
        self.assertDictEqual(result, expected)

    def test_should_transform_boost_in_search_field(self):
        tree = SearchField("spam", Boost(Word("egg"), 1))
        result = self.transformer(tree)
        expected = {"match": {"spam": {"query": 'egg', "boost": 1.0, 'type': 'phrase', 'zero_terms_query': 'none'}}}
        self.assertDictEqual(result, expected)

    def test_should_transform_fuzzy_in_word(self):
        tree = Fuzzy(Word("spam"), 1)
        result = self.transformer(tree)
        expected = {"fuzzy": {"text": {"value": 'spam', "fuzziness": 1.00}}}
        self.assertDictEqual(result, expected)

    def test_should_transform_fuzzy_in_search_field(self):
        tree = SearchField("spam", Fuzzy(Word("egg"), 1))
        result = self.transformer(tree)
        expected = {"fuzzy": {"spam": {"value": 'egg', "fuzziness": 1.0}}}
        self.assertDictEqual(result, expected)

    def test_should_transform_proximity_in_word(self):
        tree = Proximity(Phrase('"spam and eggs"'), 1)
        result = self.transformer(tree)
        expected = {"match_phrase": {
            "text": {"query": "spam and eggs", "slop": 1.0}
        }}
        self.assertDictEqual(result, expected)

    def test_should_transform_proximity_in_search_field(self):
        tree = SearchField("spam", Proximity(Phrase('"Life of Bryan"'), 1))
        result = self.transformer(tree)
        expected = {"match_phrase": {
            "spam": {"query": "Life of Bryan", "slop": 1.0}
        }}
        self.assertDictEqual(result, expected)

    def test_should_transform_range_lte_gte(self):
        tree = Range(
            low=Word('1'),
            high=Word('10'),
            include_low=True,
            include_high=True,
        )
        result = self.transformer(tree)
        expected = {"range": {"text": {"lte": '10', "gte": '1'}}}
        self.assertDictEqual(result, expected)

    def test_should_transform_range_lt_gt(self):
        tree = Range(
            low=Word('1'),
            high=Word('10'),
            include_low=False,
            include_high=False,
        )
        result = self.transformer(tree)
        expected = {"range": {"text": {"lt": '10', "gt": '1'}}}
        self.assertDictEqual(result, expected)

    def test_should_transform_range_lte_gt(self):
        tree = Range(
            low=Word('1'),
            high=Word('10'),
            include_low=True,
            include_high=False,
        )
        result = self.transformer(tree)
        expected = {"range": {"text": {"lt": '10', "gte": '1'}}}
        self.assertDictEqual(result, expected)

    def test_should_transform_range_lt_gte(self):
        tree = Range(
            low=Word('1'),
            high=Word('10'),
            include_low=False,
            include_high=True,
        )
        result = self.transformer(tree)
        expected = {"range": {"text": {"lte": '10', "gt": '1'}}}
        self.assertDictEqual(result, expected)

    def test_should_transform_range_in_search_field(self):
        tree = SearchField("spam", Range(
            low=Word('1'),
            high=Word('10'),
            include_low=True,
            include_high=False,
        ))
        result = self.transformer(tree)
        expected = {"range": {"spam": {'lt': '10', 'gte': '1'}}}
        self.assertDictEqual(result, expected)

    def test_should_transform_group(self):
        tree = AndOperation(Word("spam"), Group(AndOperation(Word("monty"), Word("python"))))
        result = self.transformer(tree)
        expected = {'bool': {'must': [
            {'term': {'text': {'value': 'spam'}}},
            {'bool': {'must': [
                {'term': {'text': {'value': 'monty'}}},
                {'term': {'text': {'value': 'python'}}},
            ]}}
        ]}}
        self.assertDictEqual(result, expected)

    def test_should_transform_field_group(self):
        tree = SearchField("spam", FieldGroup(AndOperation(Word("monty"), Word("python"))))
        result = self.transformer(tree)
        expected = {'bool': {'must': [
            {'match': {'spam': {'query': 'monty', 'type': 'phrase', 'zero_terms_query': 'all'}}},
            {'match': {'spam': {'query': 'python', 'type': 'phrase', 'zero_terms_query': 'all'}}},
        ]}}
        self.assertDictEqual(result, expected)

    def test_no_analyze_should_follow_nested(self):
        tree = SearchField(
            "author",
            FieldGroup(
                AndOperation(
                    SearchField("name", Word("Tolkien")),
                    SearchField("tag", Word("fantasy"))
                )
            )
        )
        expected = {
            'nested': {
                'path': 'author',
                'query': {
                    'bool': {
                        'must': [
                            {
                                'match': {
                                    'author.name': {
                                        'type': 'phrase',
                                        'query': 'Tolkien',
                                        'zero_terms_query': 'all'
                                    }
                                }
                            },
                            {
                                'term': {
                                    'author.tag': {
                                        'value': 'fantasy'
                                    }
                                }
                            }
                        ]
                    }
                }
            }
        }
        result = self.transformer(tree)
        self.assertDictEqual(result, expected)


class ElasticsearchTreeTransformerRealQueriesTestCase(TestCase):

    def setUp(self):

        NO_ANALYZE = [
            "type", "statut", "pays", "pays_acheteur", "pays_acheteur_display",
            "refW", "pays_execution", "dept", "region", "dept_acheteur",
            "dept_acheteur_display", "dept_execution", "flux", "sourceU",
            "url", "refA", "thes", "modele", "ii", "iqi", "idc",
            "critere_special", "auteur", "doublons", "doublons_de",
            "resultats", "resultat_de", "rectifie_par", "rectifie",
            "profils_en_cours", "profils_exclus", "profils_historiques"
        ]

        NESTED_FIELDS = {
            'author': {
                'firstname': None,
                'lastname': None,
                'book': {
                    'format': ['type'],
                    'title': None
                }
            },
            'publish': ['site']
        }

        self.transformer = ElasticsearchQueryBuilder(
            default_field="text",
            not_analyzed_fields=NO_ANALYZE,
            nested_fields=NESTED_FIELDS,
            default_operator=ElasticsearchQueryBuilder.MUST,
        )

    def test_real_situation_1(self):
        tree = parser.parse("spam:eggs")
        result = self.transformer(tree)
        expected = {'match': {'spam': {'query': 'eggs', 'type': 'phrase', 'zero_terms_query': 'none'}}}
        self.assertDictEqual(result, expected)

    def test_real_situation_2(self):
        tree = parser.parse("pays:FR AND monty:python")
        result = self.transformer(tree)
        expected = {'bool': {'must': [
            {'term': {'pays': {'value': 'FR'}}},
            {'match': {'monty': {'query': 'python', 'type': 'phrase', 'zero_terms_query': 'all'}}},
        ]}}
        self.assertDictEqual(result, expected)

    def test_real_situation_2_not_filter(self):
        tree = parser.parse("spam:de AND -monty:le AND title:alone")
        result = self.transformer(tree)
        expected = {'bool': {'must': [
            {'match': {'spam': {'query': 'de', 'type': 'phrase', 'zero_terms_query': 'all'}}},
            {'bool': {'must_not': [
                {'match': {
                    'monty': {
                        'query': 'le',
                        'type': 'phrase',
                        'zero_terms_query': 'none'
                    }}}
            ]}},
            {'match': {'title': {'query': 'alone', 'type': 'phrase', 'zero_terms_query': 'all'}}}
        ]}}
        self.assertDictEqual(result, expected)

    def test_real_situation_3(self):
        tree = parser.parse("spam:eggs AND (monty:python OR life:bryan)")
        result = self.transformer(tree)
        expected = {'bool': {'must': [
            {'match': {'spam': {'query': 'eggs', 'type': 'phrase', 'zero_terms_query': 'all'}}},
            {'bool': {'should': [
                {'match': {'monty': {'query': 'python', 'type': 'phrase', 'zero_terms_query': 'none'}}},
                {'match': {'life': {'query': 'bryan', 'type': 'phrase', 'zero_terms_query': 'none'}}},
            ]}},
        ]}}
        self.assertDictEqual(result, expected)

    def test_real_situation_4(self):
        tree = parser.parse("spam:eggs OR monty:{2 TO 4]")
        result = self.transformer(tree)
        expected = {'bool': {'should': [
            {'match': {'spam': {'query': 'eggs', 'type': 'phrase', 'zero_terms_query': 'none'}}},
            {'range': {'monty': {'lte': '4', 'gt': '2'}}},
        ]}}
        self.assertDictEqual(result, expected)

    def test_real_situation_5(self):
        tree = parser.parse("pays:FR OR objet:{2 TO 4]")
        result = self.transformer(tree)
        expected = {'bool': {'should': [
            {'term': {'pays': {'value': 'FR'}}},
            {'range': {'objet': {'lte': '4', 'gt': '2'}}},
        ]}}
        self.assertDictEqual(result, expected)

    def test_real_situation_6(self):
        tree = parser.parse("pays:FR OR monty:{2 TO 4] OR python")
        result = self.transformer(tree)
        expected = {'bool': {'should': [
            {'term': {'pays': {'value': 'FR'}}},
            {'range': {'monty': {'lte': '4', 'gt': '2'}}},
            {'match': {'text': {'query': 'python', 'type': 'phrase', 'zero_terms_query': 'none'}}},
        ]}}
        self.assertDictEqual(result, expected)

    def test_real_situation_7(self):
        tree = parser.parse(
            "pays:FR AND "
            "type:AO AND "
            "thes:(("
            "SI_FM_GC_RC_Relation_client_commerciale_courrier OR "
            "SI_FM_GC_Gestion_Projet_Documents OR "
            "SI_FM_GC_RC_Mailing_prospection_Enquete_Taxe_apprentissage OR "
            "SI_FM_GC_RC_Site_web OR "
            "SI_FM_GC_RH OR SI_FM_GC_RH_Paye OR "
            "SI_FM_GC_RH_Temps) OR NOT C91_Etranger)"
        )
        result = self.transformer(tree)
        expected = {'bool': {'must': [
            {'term': {'pays': {'value': 'FR'}}},
            {'term': {'type': {'value': 'AO'}}},
            {'bool': {'should': [
                {'bool': {'should': [
                    {'term': {'thes': {'value': 'SI_FM_GC_RC_Relation_client_commerciale_courrier'}}},
                    {'term': {'thes': {'value': 'SI_FM_GC_Gestion_Projet_Documents'}}},
                    {'term': {'thes': {'value': 'SI_FM_GC_RC_Mailing_prospection_Enquete_Taxe_apprentissage'}}},
                    {'term': {'thes': {'value': 'SI_FM_GC_RC_Site_web'}}},
                    {'term': {'thes': {'value': 'SI_FM_GC_RH'}}},
                    {'term': {'thes': {'value': 'SI_FM_GC_RH_Paye'}}},
                    {'term': {'thes': {'value': 'SI_FM_GC_RH_Temps'}}}
                ]}},
                {'bool': {'must_not': [
                    {'term': {'thes': {'value': 'C91_Etranger'}}}
                ]}}
            ]}}
        ]}}

        self.assertDictEqual(result, expected)

    def test_real_situation_8(self):
        tree = parser.parse(
            'objet:(accessibilite OR diagnosti* OR adap OR "ad ap" -(travaux OR amiante OR "hors voirie"))'
        )
        with self.assertRaises(OrAndAndOnSameLevel):
            self.transformer(tree)

    def test_real_situation_9(self):
        """
        new line and carrier field should be replace by a normal space
        """

        tree = parser.parse('spam:"monthy\r\n python"')
        result = self.transformer(tree)
        expected = {'match_phrase': {'spam': {'query': 'monthy python'}}}
        self.assertDictEqual(result, expected)

    def test_query_nested_field_without_point(self):
        """
        Can query a nested field
        """

        tree = parser.parse('author:(firstname:"François")')
        result = self.transformer(tree)
        expected = {
            "nested": {
                "path": "author",
                "query": {
                    "match_phrase": {
                        "author.firstname": {"query": "François"}
                    }
                }
            }
        }
        self.assertDictEqual(result, expected)

    def test_query_nested_field_with_point(self):
        """
        Can query a nested field
        """

        tree = parser.parse('author.firstname:"François"')
        result = self.transformer(tree)
        expected = {
            "nested": {
                "path": "author",
                "query": {
                    "match_phrase": {
                        "author.firstname": {"query": "François"}
                    }
                }
            }
        }
        self.assertDictEqual(result, expected)

    def test_query_nested_fields_with_point(self):
        """
        Can query a nested field
        """

        tree = parser.parse(
            'author.firstname:"François" AND author.lastname:"Dupont"')
        result = self.transformer(tree)
        expected = {
            "bool": {
                "must": [
                    {
                        "nested": {
                            "query": {
                                "match_phrase": {
                                    "author.firstname": {
                                        "query": "François"
                                    }
                                }
                            },
                            "path": "author"
                        }
                    },
                    {
                        "nested": {
                            "query": {
                                "match_phrase": {
                                    "author.lastname": {
                                        "query": "Dupont"
                                    }
                                }
                            },
                            "path": "author"
                        }
                    }
                ]
            }
        }
        self.assertDictEqual(result, expected)

    def test_multi_level_query_nested_fields_with_point(self):
        """
        Can query a nested field
        """

        tree = parser.parse(
            'author.book.format.type:"pdf"')
        result = self.transformer(tree)
        expected = {
            "nested": {
                "query": {
                    "nested": {
                        "query": {
                            "nested": {
                                "query": {
                                    "match_phrase": {
                                        "author.book.format.type": {
                                            "query": "pdf"
                                        }
                                    }
                                },
                                "path": "author.book.format"
                            }
                        },
                        "path": "author.book"
                    }
                },
                "path": "author"
            }
        }
        self.assertDictEqual(result, expected)

    def test_query_nested_fields_without_point(self):
        """
        Can query a nested field
        """

        tree = parser.parse(
            'author:(firstname:"François" AND lastname:"Dupont")')
        result = self.transformer(tree)
        expected = {
            "nested": {
                "path": "author",
                "query": {
                    "bool": {
                        "must": [
                            {
                                "match_phrase": {
                                    "author.firstname": {"query": "François"}
                                }
                            },
                            {
                                "match_phrase": {
                                    "author.lastname": {"query": "Dupont"}
                                }

                            }
                        ]
                    }
                }
            }
        }
        self.assertDictEqual(result, expected)

    def test_simple_multi_level_query_nested_fields_without_point(self):
        """
        Can query a nested field
        """

        tree = parser.parse(
            'author:(book:(title:"printemps"))')
        result = self.transformer(tree)
        expected = {
            "nested": {
                "path": "author",
                "query": {
                    "nested": {
                        "path":  "author.book",
                        "query":  {
                            "match_phrase": {
                                "author.book.title": {
                                    "query": "printemps"
                                }
                            }
                        }
                    }
                },
            }
        }
        self.assertDictEqual(result, expected)

    def test_multi_level_query_nested_fields_without_point(self):
        """
        Can query a nested field
        """

        tree = parser.parse(
            'author:(book:(format:(type:"pdf")))')
        result = self.transformer(tree)
        expected = {
            "nested": {
                "path": "author",
                "query": {
                    "nested": {
                        "path":  "author.book",
                        "query":  {
                            "nested": {
                                "path":  "author.book.format",
                                "query":  {
                                    "match_phrase": {
                                        "author.book.format.type": {
                                            "query": "pdf"
                                        }
                                    }
                                }
                            }
                        }
                    }
                },
            }
        }
        self.assertDictEqual(result, expected)

    def test_multi_level_operation_query_nested_fields_without_point(self):
        """
        Can query a nested field
        """

        tree = parser.parse(
            'author:(book:(format:(type:"pdf" OR type:"epub")))')
        result = self.transformer(tree)
        expected = {
            "nested": {
                "query": {
                    "nested": {
                        "query": {
                            "nested": {
                                "query": {
                                    "bool": {
                                        "should": [
                                            {
                                                "match_phrase": {
                                                    "author.book.format.type": {
                                                        "query": "pdf"
                                                    }
                                                }
                                            },
                                            {
                                                "match_phrase": {
                                                    "author.book.format.type": {
                                                        "query": "epub"
                                                    }
                                                }
                                            }
                                        ]
                                    }
                                },
                                "path": "author.book.format"
                            }
                        },
                        "path": "author.book"
                    }
                },
                "path": "author"
            }
        }
        self.assertDictEqual(result, expected)

    def test_multi_level_operation_query_nested_fields_with_point(self):
        """
        Can query a nested field
        """

        tree = parser.parse(
            'author.book.format.type:"pdf" OR author.book.format.type:"epub"')
        result = self.transformer(tree)
        expected = {
            "bool": {
                "should": [
                    {
                        "nested": {
                            "query": {
                                "nested": {
                                    "query": {
                                        "nested": {
                                            "query": {
                                                "match_phrase": {
                                                    "author.book.format.type": {
                                                        "query": "pdf"
                                                    }
                                                }
                                            },
                                            "path": "author.book.format"
                                        }
                                    },
                                    "path": "author.book"
                                }
                            },
                            "path": "author"
                        }
                    },
                    {
                        "nested": {
                            "query": {
                                "nested": {
                                    "query": {
                                        "nested": {
                                            "query": {
                                                "match_phrase": {
                                                    "author.book.format.type": {
                                                        "query": "epub"
                                                    }
                                                }
                                            },
                                            "path": "author.book.format"
                                        }
                                    },
                                    "path": "author.book"
                                }
                            },
                            "path": "author"
                        }
                    }
                ]
            }
        }
        self.assertDictEqual(result, expected)

    def test_complex_multi_level_operation_query_nested_fields(self):
        """
        Can query a nested field
        """

        tree = parser.parse(
            'author:book:(title:"Hugo" AND format:type:("pdf" OR "epub"))'
        )
        result = self.transformer(tree)
        expected = {
            "nested": {
                "path": "author",
                "query": {
                    "nested": {
                        "path": "author.book",
                        "query": {
                            "bool": {
                                "must": [
                                    {
                                        "match_phrase": {
                                            "author.book.title": {
                                                "query": "Hugo"
                                            }
                                        }
                                    },
                                    {
                                        "nested": {
                                            "path": "author.book.format",
                                            "query": {
                                                "bool": {
                                                    "should": [
                                                        {
                                                            "match_phrase": {
                                                                "author.book.format.type": {
                                                                    "query": "pdf"
                                                                }
                                                            }
                                                        },
                                                        {
                                                            "match_phrase": {
                                                                "author.book.format.type": {
                                                                    "query": "epub"
                                                                }
                                                            }
                                                        }
                                                    ]
                                                }
                                            }
                                        }
                                    }
                                ]
                            }
                        }
                    }
                }
            }
        }
        self.assertDictEqual(result, expected)
