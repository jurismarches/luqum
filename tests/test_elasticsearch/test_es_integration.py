from unittest import TestCase, skipIf

from luqum.parser import parser

from .es_integration_utils import (
    add_book_data, book_query_builder, book_search, get_es, remove_book_index,
)


@skipIf(get_es() is None, "Skipping ES test as I can't reach ES")
class LuqumRequestTestCase(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.es_client = get_es()
        if cls.es_client is None:
            return
        cls.es_builder = book_query_builder(cls.es_client)
        cls.search = book_search(cls.es_client)
        add_book_data(cls.es_client)

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
        remove_book_index(cls.es_client)
