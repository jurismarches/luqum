import abc
import re


class JsonSerializableMixin:

    @property
    @abc.abstractmethod
    def json(self):
        return


class AbstractEItem(JsonSerializableMixin):

    boost = None
    _fuzzy = None

    _KEYS_TO_ADD = ('boost', 'fuzziness', )
    ADDITIONAL_KEYS_TO_ADD = ()

    def __init__(self, no_analyze, method='term', field='text'):
        self._method = method
        self.field = field
        self._no_analyze = no_analyze

    @property
    def json(self):
        json = {self.method: {self.field: {}}}
        inner_json = json[self.method][self.field]

        # add base conf
        keys = self._KEYS_TO_ADD + self.ADDITIONAL_KEYS_TO_ADD
        for key in keys:
            value = getattr(self, key)
            if value is not None:
                if key == 'value' and self.method == 'match':
                    inner_json['query'] = value
                elif key == 'value' and self.method == 'query_string':
                    inner_json['query'] = value
                    inner_json['analyze_wildcard'] = True
                    inner_json['default_field'] = self.field
                    inner_json['allow_leading_wildcard'] = True
                else:
                    inner_json[key] = value

        if self.method == 'query_string':
            json[self.method] = json[self.method].pop(self.field)

        return json

    @property
    def fuzziness(self):
        return self._fuzzy

    @property
    def method(self):
        if self.field in self._no_analyze and any(char in getattr(self, 'value', '') for char in ['*', '?']):
            return 'wildcard'
        elif self.field not in self._no_analyze and any(char in getattr(self, 'value', '') for char in ['*', '?']):
            return 'query_string'
        elif self.field not in self._no_analyze and self._method == 'term':
            return 'match'
        return self._method

    @fuzziness.setter
    def fuzziness(self, fuzzy):
        self._method = 'fuzzy'
        self._fuzzy = fuzzy


class EWord(AbstractEItem):

    ADDITIONAL_KEYS_TO_ADD = ('value', )

    def __init__(self, value, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.value = value

    @property
    def json(self):
        if self.value == '*':
            return {"exists": {"field": self.field}}
        return super().json


class EPhrase(AbstractEItem):

    ADDITIONAL_KEYS_TO_ADD = ('query',)
    _proximity = None

    def __init__(self, phrase, *args, **kwargs):
        super().__init__(method='match_phrase', *args, **kwargs)
        self.query = re.search(r'"(?P<value>.+)"', phrase).group("value")

    @property
    def slop(self):
        return self._proximity

    @slop.setter
    def slop(self, slop):
        self._proximity = slop
        self.ADDITIONAL_KEYS_TO_ADD += ('slop', )


class ERange(AbstractEItem):

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

    def __init__(self, items):
        self.items = items

    @property
    def json(self):
        return {'bool': {self.operation: [item.json for item in self.items]}}


class EShould(AbstractEOperation):
    operation = 'should'


class EMust(AbstractEOperation):
    operation = 'must'


class EMustNot(AbstractEOperation):
    operation = 'must_not'


class ElasticSearchItemFactory:

    def __init__(self, no_analyze):
        self._no_analyze = no_analyze

    def build(self, cls, *args, **kwargs):
        if issubclass(cls, AbstractEItem):
            return cls(no_analyze=self._no_analyze, *args, **kwargs)
        else:
            return cls(*args, **kwargs)
