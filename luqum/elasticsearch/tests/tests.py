from unittest import TestCase

from luqum.parser import parser
from luqum.tree import (
    AndOperation, Word, Prohibit, OrOperation, Not, Phrase, SearchField,
    UnknownOperation, Boost, Fuzzy, Proximity, Range, Group, FieldGroup,
    Plus)
from ..visitor import ElasticsearchQueryBuilder


class ElasticsearchTreeTransformerTestCase(TestCase):

    def setUp(self):
        self.transformer = ElasticsearchQueryBuilder(default_field="text")

    def test_should_transform_and(self):
        tree = AndOperation(Word('spam'), Word('eggs'))
        result = self.transformer.visit(tree).json
        expected = {'bool': {'must': [
            {"term": {"text": {"value": 'spam'}}},
            {"term": {"text": {"value": 'eggs'}}},
        ]}}
        self.assertDictEqual(result, expected)

    def test_should_transform_plus(self):
        tree = Plus(Word("spam"))
        result = self.transformer.visit(tree).json
        expected = {'bool': {'must': [
            {"term": {"text": {"value": 'spam'}}},
        ]}}
        self.assertDictEqual(result, expected)

    def test_should_transform_or(self):
        tree = OrOperation(Word('spam'), Word('eggs'))
        result = self.transformer.visit(tree).json
        expected = {'bool': {'should': [
            {"term": {"text": {"value": 'spam'}}},
            {"term": {"text": {"value": 'eggs'}}},
        ]}}
        self.assertDictEqual(result, expected)

    def test_should_transform_prohibit(self):
        tree = Prohibit(Word("spam"))
        result = self.transformer.visit(tree).json
        expected = {'bool': {'must_not': [
            {"term": {"text": {"value": 'spam'}}},
        ]}}
        self.assertDictEqual(result, expected)

    def test_should_transform_not(self):
        tree = Not(Word('spam'))
        result = self.transformer.visit(tree).json
        expected = {'bool': {'must_not': [
            {"term": {"text": {"value": 'spam'}}},
        ]}}
        self.assertDictEqual(result, expected)

    def test_should_transform_word(self):
        tree = Word('spam')
        result = self.transformer.visit(tree).json
        expected = {"term": {"text": {"value": 'spam'}}}
        self.assertDictEqual(result, expected)

    def test_should_transform_word_with_custom_search_field(self):
        transformer = ElasticsearchQueryBuilder(default_field="custom")
        tree = Word('spam')
        result = transformer.visit(tree).json
        expected = {"term": {"custom": {"value": 'spam'}}}
        self.assertDictEqual(result, expected)

    def test_should_transform_phrase(self):
        tree = Phrase('"spam eggs"')
        result = self.transformer.visit(tree).json
        expected = {"match_phrase": {"text": {"query": 'spam eggs'}}}
        self.assertDictEqual(result, expected)

    def test_should_transform_phrase_with_custom_search_field(self):
        transformer = ElasticsearchQueryBuilder(default_field="custom")
        tree = Phrase('"spam eggs"')
        result = transformer.visit(tree).json
        expected = {"match_phrase": {"custom": {"query": 'spam eggs'}}}
        self.assertDictEqual(result, expected)

    def test_should_transform_phrase_with_search_field(self):
        tree = SearchField('monthy', Phrase('"spam eggs"'))
        result = self.transformer.visit(tree).json
        expected = {"match_phrase": {"monthy": {"query": 'spam eggs'}}}
        self.assertDictEqual(result, expected)

    def test_should_transform_search_field(self):
        tree = SearchField("pays", Word("spam"))
        result = self.transformer.visit(tree).json
        expected = {"term": {"pays": {"value": 'spam'}}}
        self.assertDictEqual(result, expected)

    def test_should_transform_unknown_operation_default(self):
        tree = UnknownOperation(Word("spam"), Word("eggs"))
        result = self.transformer.visit(tree).json
        expected = {'bool': {'should': [
            {"term": {"text": {"value": 'spam'}}},
            {"term": {"text": {"value": 'eggs'}}},
        ]}}
        self.assertDictEqual(result, expected)

    def test_should_transform_unknown_operation_default_must(self):
        transformer = ElasticsearchQueryBuilder(
            default_operator=ElasticsearchQueryBuilder.MUST
        )
        tree = UnknownOperation(Word("spam"), Word("eggs"))
        result = transformer.visit(tree).json
        expected = {'bool': {'must': [
            {"term": {"text": {"value": 'spam'}}},
            {"term": {"text": {"value": 'eggs'}}},
        ]}}
        self.assertDictEqual(result, expected)

    def test_should_transform_unknown_operation_default_should(self):
        transformer = ElasticsearchQueryBuilder(
            default_operator=ElasticsearchQueryBuilder.SHOULD
        )
        tree = UnknownOperation(Word("spam"), Word("eggs"))
        result = transformer.visit(tree).json
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
        result = self.transformer.visit(tree).json
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
        result = self.transformer.visit(tree).json
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
        result = self.transformer.visit(tree).json
        expected = {'bool': {'must': [
            {"term": {"text": {"value": 'spam'}}},
            {'bool': {'should': [
                {"term": {"text": {"value": 'eggs'}}},
                {'bool': {'must': [
                    {"term": {"text": {"value": 'monthy'}}},
                    {"term": {"text": {"value": 'python'}}}
                ]}}
                ]}}
            ]}}
        self.assertDictEqual(result, expected)

    def test_should_transform_boost_in_word(self):
        tree = Boost(Word("spam"), 1)
        result = self.transformer.visit(tree).json
        expected = {"term": {"text": {"value": 'spam', "boost": 1.00}}}
        self.assertDictEqual(result, expected)

    def test_should_transform_boost_in_search_field(self):
        tree = SearchField("spam", Boost(Word("egg"), 1))
        result = self.transformer.visit(tree).json
        expected = {"term": {"spam": {"value": 'egg', "boost": 1.0}}}
        self.assertDictEqual(result, expected)

    def test_should_transform_fuzzy_in_word(self):
        tree = Fuzzy(Word("spam"), 1)
        result = self.transformer.visit(tree).json
        expected = {"fuzzy": {"text": {"value": 'spam', "fuzziness": 1.00}}}
        self.assertDictEqual(result, expected)

    def test_should_transform_fuzzy_in_search_field(self):
        tree = SearchField("spam", Fuzzy(Word("egg"), 1))
        result = self.transformer.visit(tree).json
        expected = {"fuzzy": {"spam": {"value": 'egg', "fuzziness": 1.0}}}
        self.assertDictEqual(result, expected)

    def test_should_transform_proximity_in_word(self):
        tree = Proximity(Phrase('"spam and eggs"'), 1)
        result = self.transformer.visit(tree).json
        expected = {"match_phrase": {
            "text": {"query": "spam and eggs", "slop": 1.0}
        }}
        self.assertDictEqual(result, expected)

    def test_should_transform_proximity_in_search_field(self):
        tree = SearchField("spam", Proximity(Phrase('"Life of Bryan"'), 1))
        result = self.transformer.visit(tree).json
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
        result = self.transformer.visit(tree).json
        expected = {"range": {"text": {"lte": '10', "gte": '1'}}}
        self.assertDictEqual(result, expected)

    def test_should_transform_range_lt_gt(self):
        tree = Range(
            low=Word('1'),
            high=Word('10'),
            include_low=False,
            include_high=False,
        )
        result = self.transformer.visit(tree).json
        expected = {"range": {"text": {"lt": '10', "gt": '1'}}}
        self.assertDictEqual(result, expected)

    def test_should_transform_range_lte_gt(self):
        tree = Range(
            low=Word('1'),
            high=Word('10'),
            include_low=True,
            include_high=False,
        )
        result = self.transformer.visit(tree).json
        expected = {"range": {"text": {"lt": '10', "gte": '1'}}}
        self.assertDictEqual(result, expected)

    def test_should_transform_range_lt_gte(self):
        tree = Range(
            low=Word('1'),
            high=Word('10'),
            include_low=False,
            include_high=True,
        )
        result = self.transformer.visit(tree).json
        expected = {"range": {"text": {"lte": '10', "gt": '1'}}}
        self.assertDictEqual(result, expected)

    def test_should_transform_range_in_search_field(self):
        tree = SearchField("spam", Range(
            low=Word('1'),
            high=Word('10'),
            include_low=True,
            include_high=False,
        ))
        result = self.transformer.visit(tree).json
        expected = {"range": {"spam": {'lt': '10', 'gte': '1'}}}
        self.assertDictEqual(result, expected)

    def test_should_transform_group(self):
        tree = AndOperation(Word("spam"), Group(AndOperation(Word("monty"), Word("python"))))
        result = self.transformer.visit(tree).json
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
        result = self.transformer.visit(tree).json
        expected = {'bool': {'must': [
            {'term': {'spam': {'value': 'monty'}}},
            {'term': {'spam': {'value': 'python'}}},
        ]}}
        self.assertDictEqual(result, expected)

    def test_real_situation_1(self):
        tree = parser.parse("spam:eggs")
        result = self.transformer.visit(tree).json
        expected = {'term': {'spam': {'value': 'eggs'}}}
        self.assertDictEqual(result, expected)

    def test_real_situation_2(self):
        tree = parser.parse("spam:eggs AND monty:python")
        result = self.transformer.visit(tree).json
        expected = {'bool': {'must': [
            {'term': {'spam': {'value': 'eggs'}}},
            {'term': {'monty': {'value': 'python'}}},
        ]}}
        self.assertDictEqual(result, expected)

    def test_real_situation_3(self):
        tree = parser.parse("spam:eggs AND (monty:python OR life:bryan)")
        result = self.transformer.visit(tree).json
        expected = {'bool': {'must': [
            {'term': {'spam': {'value': 'eggs'}}},
            {'bool': {'should': [
                {'term': {'monty': {'value': 'python'}}},
                {'term': {'life': {'value': 'bryan'}}},
            ]}},
        ]}}
        self.assertDictEqual(result, expected)

    def test_real_situation_4(self):
        tree = parser.parse("spam:eggs OR monty:{2 TO 4]")
        result = self.transformer.visit(tree).json
        expected = {'bool': {'should': [
            {'term': {'spam': {'value': 'eggs'}}},
            {'range': {'monty': {'lte': '4', 'gt': '2'}}},
        ]}}
        self.assertDictEqual(result, expected)

    def test_real_situation_5(self):
        tree = parser.parse("spam:eggs OR monty:{2 TO 4]")
        result = self.transformer.visit(tree).json
        expected = {'bool': {'should': [
            {'term': {'spam': {'value': 'eggs'}}},
            {'range': {'monty': {'lte': '4', 'gt': '2'}}},
        ]}}
        self.assertDictEqual(result, expected)

    def test_real_situation_6(self):
        tree = parser.parse("spam:eggs OR monty:{2 TO 4] OR python")
        result = self.transformer.visit(tree).json
        expected = {'bool': {'should': [
            {'term': {'spam': {'value': 'eggs'}}},
            {'range': {'monty': {'lte': '4', 'gt': '2'}}},
            {'term': {'text': {'value': 'python'}}},
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
        result = self.transformer.visit(tree).json
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
