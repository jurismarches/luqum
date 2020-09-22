from unittest import TestCase

from luqum.elasticsearch.tree import EShould, EWord


class TestItems(TestCase):

    def test_should_operation_options(self):
        op = EShould(items=[EWord(q="a"), EWord(q="b"), EWord(q="c")], minimum_should_match=2)
        self.assertEqual(
            op.json,
            {'bool': {
                'should': [
                    {'term': {'': {'value': 'a'}}},
                    {'term': {'': {'value': 'b'}}},
                    {'term': {'': {'value': 'c'}}},
                ],
                'minimum_should_match': 2,
            }},
        )
