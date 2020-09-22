from unittest import TestCase

from luqum.check import LuceneCheck, CheckNestedFields
from luqum.exceptions import NestedSearchFieldException, ObjectSearchFieldException
from luqum.parser import parser
from luqum.tree import (
    SearchField, FieldGroup, Group, Word, Phrase, Proximity, Fuzzy, Boost, Range,
    Not, AndOperation, OrOperation, Plus, Prohibit)


class TestCheck(TestCase):

    def test_check_ok(self):
        query = (
            AndOperation(
                SearchField(
                    "f",
                    FieldGroup(
                        AndOperation(
                            Boost(Proximity(Phrase('"foo bar"'), 4), "4.2"),
                            Prohibit(Range("100", "200"))))),
                Group(
                    OrOperation(
                        Fuzzy(Word("baz"), ".8"),
                        Plus(Word("fizz"))))))
        check = LuceneCheck()
        self.assertTrue(check(query))
        self.assertEqual(check.errors(query), [])
        check = LuceneCheck(zeal=1)
        self.assertTrue(check(query))
        self.assertEqual(check.errors(query), [])

    def test_bad_fieldgroup(self):
        check = LuceneCheck()
        query = FieldGroup(Word("foo"))
        self.assertFalse(check(query))
        self.assertEqual(len(check.errors(query)), 1)
        self.assertIn("FieldGroup misuse", check.errors(query)[0])

        query = OrOperation(
            FieldGroup(Word("bar")),
            Word("foo"))
        self.assertFalse(check(query))
        self.assertEqual(len(check.errors(query)), 1)
        self.assertIn("FieldGroup misuse", check.errors(query)[0])

    def test_bad_group(self):
        check = LuceneCheck()
        query = SearchField("f", Group(Word("foo")))
        self.assertFalse(check(query))
        self.assertEqual(len(check.errors(query)), 2)  # one for bad expr, one for misuse
        self.assertIn("Group misuse", "".join(check.errors(query)))

    def test_zealous_or_not_prohibit(self):
        query = (
            OrOperation(
                Prohibit(Word("foo")),
                Word("bar")))
        check_zealous = LuceneCheck(zeal=1)
        self.assertFalse(check_zealous(query))
        self.assertIn("inconsistent", check_zealous.errors(query)[0])
        check_easy_going = LuceneCheck()
        self.assertTrue(check_easy_going(query))

    def test_zealous_or_not(self):
        query = (
            OrOperation(
                Not(Word("foo")),
                Word("bar")))
        check_zealous = LuceneCheck(zeal=1)
        self.assertFalse(check_zealous(query))
        self.assertIn("inconsistent", check_zealous.errors(query)[0])
        check_easy_going = LuceneCheck()
        self.assertTrue(check_easy_going(query))

    def test_bad_field_name(self):
        check = LuceneCheck()
        query = SearchField("foo*", Word("bar"))
        self.assertFalse(check(query))
        self.assertEqual(len(check.errors(query)), 1)
        self.assertIn("not a valid field name", check.errors(query)[0])

    def test_bad_field_expr(self):
        check = LuceneCheck()
        query = SearchField("foo", Prohibit(Word("bar")))
        self.assertFalse(check(query))
        self.assertEqual(len(check.errors(query)), 1)
        self.assertIn("not valid", check.errors(query)[0])

    def test_word_space(self):
        check = LuceneCheck()
        query = Word("foo bar")
        self.assertFalse(check(query))
        self.assertEqual(len(check.errors(query)), 1)
        self.assertIn("space", check.errors(query)[0])

    def test_invalid_characters_in_word_value(self):
        query = Word("foo/bar")
        # Passes if zeal == 0
        check = LuceneCheck()
        self.assertTrue(check(query))
        self.assertEqual(len(check.errors(query)), 0)
        # But not if zeal == 1
        check = LuceneCheck(zeal=1)
        self.assertFalse(check(query))
        self.assertEqual(len(check.errors(query)), 1)
        self.assertIn("Invalid characters", check.errors(query)[0])

    def test_fuzzy_negative_degree(self):
        check = LuceneCheck()
        query = Fuzzy(Word("foo"), "-4.1")
        self.assertFalse(check(query))
        self.assertEqual(len(check.errors(query)), 1)
        self.assertIn("invalid degree", check.errors(query)[0])

    def test_fuzzy_non_word(self):
        check = LuceneCheck()
        query = Fuzzy(Phrase('"foo bar"'), "2")
        self.assertFalse(check(query))
        self.assertEqual(len(check.errors(query)), 1)
        self.assertIn("single term", check.errors(query)[0])

    def test_proximity_non_phrase(self):
        check = LuceneCheck()
        query = Proximity(Word("foo"), "2")
        self.assertFalse(check(query))
        self.assertEqual(len(check.errors(query)), 1)
        self.assertIn("phrase", check.errors(query)[0])

    def test_unknown_item_type(self):
        check = LuceneCheck()
        query = AndOperation("foo", 2)
        self.assertFalse(check(query))
        self.assertEqual(len(check.errors(query)), 2)
        self.assertIn("Unknown item type", check.errors(query)[0])
        self.assertIn("Unknown item type", check.errors(query)[1])


class CheckVisitorTestCase(TestCase):

    NESTED_FIELDS = {
        'author': {
            'firstname': {},
            'book': {
                'title': {},
                'format': {
                    'type': {}
                }
            }
        },
        'collection.keywords': {  # nested field inside an object field
            'key': {},
            'more_info.linked': {  # again nested field inside an object field
                'key': {}
            },
        },
    }

    OBJECT_FIELDS = [
        'author.birth.city',
        'collection.title', 'collection.ref', 'collection.keywords.more_info.revision']

    SUB_FIELDS = [
        'foo.english',
        'author.book.title.raw',
    ]

    def setUp(self):
        self.checker = CheckNestedFields(nested_fields=self.NESTED_FIELDS)
        self.strict_checker = CheckNestedFields(
            nested_fields=self.NESTED_FIELDS,
            object_fields=self.OBJECT_FIELDS,
            sub_fields=self.SUB_FIELDS,
        )

    def test_correct_nested_lucene_query_column_not_raise(self):
        tree = parser.parse('author:book:title:"foo" AND '
                            'author:book:format:type: "pdf"')
        self.strict_checker(tree)

    def test_correct_object_lucene_query_column_not_raise(self):
        tree = parser.parse('author:birth:city:"foo" AND '
                            'collection:(ref:"foo" AND title:"bar")')
        self.strict_checker(tree)
        self.checker(tree)
        self.assertIsNotNone(tree)

    def test_correct_subfield_lucene_query_column_not_raises(self):
        tree = parser.parse('foo:english:"foo" AND '
                            'author:book:title:raw:"pdf"')
        self.strict_checker(tree)

    def test_correct_nested_lucene_query_with_point_not_raise(self):
        tree = parser.parse('author.book.title:"foo" AND '
                            'author.book.format.type:"pdf"')
        self.strict_checker(tree)
        self.assertIsNotNone(tree)

    def test_correct_object_lucene_query_with_point_not_raise(self):
        tree = parser.parse('author.birth.city:"foo" AND '
                            'collection.ref:"foo"')
        self.strict_checker(tree)
        self.checker(tree)
        self.assertIsNotNone(tree)

    def test_correct_subfield_lucene_query_with_point_not_raises(self):
        tree = parser.parse('foo.english:"foo" AND '
                            'author.book.title.raw:"pdf"')
        self.strict_checker(tree)

    def test_correct_object_mix_do_not_raise(self):
        tree = parser.parse('author:(birth.city:"foo" AND book.title:"bar")')
        self.strict_checker(tree)
        self.checker(tree)
        self.assertIsNotNone(tree)

    def test_incorrect_nested_lucene_query_column_raise(self):
        tree = parser.parse('author:gender:"Mr" AND '
                            'author:book:format:type:"pdf"')
        with self.assertRaises(ObjectSearchFieldException) as e:
            self.strict_checker(tree)
        self.assertIn('author.gender', str(e.exception))

    def test_incorrect_nested_lucene_query_with_point_raise(self):
        tree = parser.parse('author.gender:"Mr" AND '
                            'author.book.format.type:"pdf"')
        with self.assertRaises(ObjectSearchFieldException) as e:
            self.strict_checker(tree)
        self.assertIn('"author.gender"', str(e.exception))

    def test_correct_nested_lucene_query_with_and_column_not_raise(self):
        tree = parser.parse(
            'author:(book.title:"foo" OR book.title:"bar")')
        self.checker(tree)
        self.assertIsNotNone(tree)

    def test_complex_subfield_not_raises(self):
        tree = parser.parse(
            'author:(book.title.raw:"foo" OR book.title.raw:"bar")')
        self.checker(tree)
        self.assertIsNotNone(tree)

    def test_simple_query_with_a_nested_field_should_raise(self):
        tree = parser.parse('author:"foo"')
        with self.assertRaises(NestedSearchFieldException) as e:
            self.strict_checker(tree)
        self.assertIn('"author"', str(e.exception))

    def test_simple_query_with_a_multi_nested_field_should_raise(self):
        tree = parser.parse('author:book:"foo"')
        with self.assertRaises(NestedSearchFieldException) as e:
            self.strict_checker(tree)
        self.assertIn('"author.book"', str(e.exception))

    def test_complex_query_with_a_multi_nested_field_should_raise(self):
        tree = parser.parse('author:test OR author.firstname:"Hugo"')
        with self.assertRaises(NestedSearchFieldException) as e:
            self.strict_checker(tree)
        self.assertIn('"author"', str(e.exception))

    def test_complex_query_column_with_a_multi_nested_field_should_raise(self):
        tree = parser.parse('author:("test" AND firstname:Hugo)')
        with self.assertRaises(NestedSearchFieldException) as e:
            self.strict_checker(tree)
        self.assertIn('"author"', str(e.exception))

    def test_complex_mix(self):
        tree = parser.parse(
            'collection:(title:"foo" AND keywords.more_info:(linked.key:"bar" revision:"test"))')
        self.strict_checker(tree)
        self.checker(tree)
        self.assertIsNotNone(tree)

    def test_complex_mix_raise(self):
        tree = parser.parse(
            'collection:(title:"foo" AND keywords.more_info:(linked:"bar" revision:"test"))')
        with self.assertRaises(NestedSearchFieldException) as e:
            self.strict_checker(tree)
        self.assertIn('"collection.keywords.more_info.linked"', str(e.exception))
        self.assertIsNotNone(tree)

    def test_incomplete_object_field_raise(self):
        tree = parser.parse('collection.keywords.more_info:"foo"')
        with self.assertRaises(NestedSearchFieldException) as e:
            self.strict_checker(tree)
        self.assertIn('"collection.keywords.more_info"', str(e.exception))

        tree = parser.parse('author:birth:"foo"')
        with self.assertRaises(NestedSearchFieldException) as e:
            self.strict_checker(tree)
        self.assertIn('"author.birth"', str(e.exception))
