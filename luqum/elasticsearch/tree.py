import abc
import re


class JsonSerializableMixin:
    """
    Mixin to force subclasses to implement the json method
    """

    @property
    @abc.abstractmethod
    def json(self):
        return


class AbstractEItem(JsonSerializableMixin):
    """
    Base item element to build the "item" json
    For instance : {"term": {"field": {"value": "query"}}}
    """

    boost = None
    _fuzzy = None

    _KEYS_TO_ADD = ('boost', 'fuzziness', )
    ADDITIONAL_KEYS_TO_ADD = ()

    def __init__(self, no_analyze=None, method='term', field='text'):
        self._method = method
        self.field = field
        self._no_analyze = no_analyze if no_analyze else []

    @property
    def json(self):

        inner_json = {}
        if self.method == 'query_string':
            json = {self.method: inner_json}
        else:
            json = {self.method: {self.field: inner_json}}

        # add base conf
        keys = self._KEYS_TO_ADD + self.ADDITIONAL_KEYS_TO_ADD
        for key in keys:
            value = getattr(self, key)
            if value is not None:
                if key == 'q' and self.method == 'match':
                    inner_json['query'] = value
                    inner_json['type'] = 'phrase'
                    inner_json['zero_terms_query'] = 'all'
                elif key == 'q' and self.method == 'query_string':
                    inner_json['query'] = value
                    inner_json['analyze_wildcard'] = True
                    inner_json['default_field'] = self.field
                    inner_json['allow_leading_wildcard'] = True
                elif key == 'q':
                    inner_json['value'] = value
                else:
                    inner_json[key] = value
        return json

    @property
    def fuzziness(self):
        return self._fuzzy

    @fuzziness.setter
    def fuzziness(self, fuzzy):
        self._method = 'fuzzy'
        self._fuzzy = fuzzy

    def _value_has_wildcard_char(self):
        return any(char in getattr(self, 'q', '') for char in ['*', '?'])

    def _is_analyzed(self):
        return self.field in self._no_analyze

    @property
    def method(self):
        if self._is_analyzed() and self._value_has_wildcard_char():
            return 'wildcard'
        elif not self._is_analyzed() and self._value_has_wildcard_char():
            return 'query_string'
        elif not self._is_analyzed() and self._method == 'term':
            return 'match'
        return self._method


class EWord(AbstractEItem):
    """
    Build a word
    >>> from unittest import TestCase
    >>> TestCase().assertDictEqual(
    ...     EWord(q='test').json,
    ...     {'match': {'text': {
    ...         'zero_terms_query': 'all',
    ...         'type': 'phrase',
    ...         'query': 'test'
    ...     }}},
    ... )
    """

    ADDITIONAL_KEYS_TO_ADD = ('q', )

    def __init__(self, q, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.q = q

    @property
    def json(self):
        if self.q == '*':
            return {"exists": {"field": self.field}}
        return super().json


class EPhrase(AbstractEItem):
    """
    Build a phrase
    >>> from unittest import TestCase
    >>> TestCase().assertDictEqual(
    ...     EPhrase(phrase='"another test"').json,
    ...     {'match_phrase': {'text': {'query': 'another test'}}},
    ... )
    """

    ADDITIONAL_KEYS_TO_ADD = ('query',)
    _proximity = None

    def __init__(self, phrase, *args, **kwargs):
        super().__init__(method='match_phrase', *args, **kwargs)
        phrase = self._replace_CR_and_LF_by_a_whitespace(phrase)
        self.query = self._remove_double_quotes(phrase)

    def _replace_CR_and_LF_by_a_whitespace(self, phrase):
        return re.sub(r'\s+', ' ', phrase)

    def _remove_double_quotes(self, phrase):
        return re.search(r'"(?P<value>.+)"', phrase).group("value")

    @property
    def slop(self):
        return self._proximity

    @slop.setter
    def slop(self, slop):
        self._proximity = slop
        self.ADDITIONAL_KEYS_TO_ADD += ('slop', )


class ERange(AbstractEItem):
    """
    Build a range
    >>> from unittest import TestCase
    >>> TestCase().assertDictEqual(
    ...     ERange(lt=100, gte=10).json,
    ...     {'range': {'text': {'lt': 100, 'gte': 10}}},
    ... )
    """

    def __init__(self, lt=None, lte=None, gt=None, gte=None, *args, **kwargs):
        super().__init__(method='range', *args, **kwargs)
        if lt and lt != '*':
            self.lt = lt
            self.ADDITIONAL_KEYS_TO_ADD += ('lt', )
        elif lte and lte != '*':
            self.lte = lte
            self.ADDITIONAL_KEYS_TO_ADD += ('lte', )
        if gt and gt != '*':
            self.gt = gt
            self.ADDITIONAL_KEYS_TO_ADD += ('gt', )
        elif gte and gte != '*':
            self.gte = gte
            self.ADDITIONAL_KEYS_TO_ADD += ('gte', )


class AbstractEOperation(JsonSerializableMixin):
    """
    Abstract operation taking care of the json build
    """

    def __init__(self, items):
        self.items = items

    @property
    def json(self):
        return {'bool': {self.operation: [item.json for item in self.items]}}


class EShould(AbstractEOperation):
    """
    Build a should operation
    >>> from unittest import TestCase
    >>> json = EShould(
    ...     items=[EPhrase('"monty python"'), EPhrase('"spam eggs"')]
    ... ).json
    >>> TestCase().assertDictEqual(
    ...     json,
    ...     {'bool': {'should': [
    ...         {'match_phrase': {'text': {'query': 'monty python'}}},
    ...         {'match_phrase': {'text': {'query': 'spam eggs'}}},
    ...     ]}}
    ... )
    """
    operation = 'should'


class EMust(AbstractEOperation):
    """
    Build a must operation
    >>> from unittest import TestCase
    >>> json = EMust(
    ...     items=[EPhrase('"monty python"'), EPhrase('"spam eggs"')]
    ... ).json
    >>> TestCase().assertDictEqual(
    ...     json,
    ...     {'bool': {'must': [
    ...         {'match_phrase': {'text': {'query': 'monty python'}}},
    ...         {'match_phrase': {'text': {'query': 'spam eggs'}}},
    ...     ]}}
    ... )
    """
    operation = 'must'


class EMustNot(AbstractEOperation):
    """
    Build a must not operation
    >>> from unittest import TestCase
    >>> TestCase().assertDictEqual(
    ...     EMustNot(items=[EPhrase('"monty python"')]).json,
    ...     {'bool': {'must_not': [
    ...         {'match_phrase': {'text': {'query': 'monty python'}}},
    ...     ]}}
    ... )
    """
    operation = 'must_not'


class ElasticSearchItemFactory:
    """
    Factory to preconfigure EItems and EOperation
    At the moment, it's only used to pass the _no_analyze field
    >>> from unittest import TestCase
    >>> factory = ElasticSearchItemFactory(no_analyze=['text'])
    >>> word = factory.build(EWord, q='test')
    >>> TestCase().assertDictEqual(
    ...     word.json,
    ...     {'term': {'text': {'value': 'test'}}},
    ... )
    """

    def __init__(self, no_analyze):
        self._no_analyze = no_analyze

    def build(self, cls, *args, **kwargs):
        if issubclass(cls, AbstractEItem):
            return cls(no_analyze=self._no_analyze, *args, **kwargs)
        else:
            return cls(*args, **kwargs)
