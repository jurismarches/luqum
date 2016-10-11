import abc
import re


NO_ANALYZE = [
    "type", "statut", "pays", "pays_acheteur", "pays_acheteur_display", "refW",
    "pays_execution", "dept", "region", "dept_acheteur",
    "dept_acheteur_display", "dept_execution", "flux", "sourceU", "url",
    "refA", "thes", "modele", "ii", "iqi", "idc", "critere_special", "auteur",
    "doublons", "doublons_de", "resultats", "resultat_de", "rectifie_par",
    "rectifie", "profils_en_cours", "profils_exclus", "profils_historiques"
]

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

    def __init__(self, method='term', field='text'):
        self._method = method
        self.field = field

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
                else:
                    inner_json[key] = value
        return json

    @property
    def fuzziness(self):
        return self._fuzzy

    @property
    def method(self):
        if any(char in getattr(self, 'value', '') for char in ['*', '?']):
            return 'wildcard'
        elif self.field not in NO_ANALYZE and self._method == 'term':
            return 'match'
        return self._method

    @fuzziness.setter
    def fuzziness(self, fuzzy):
        self._method = 'fuzzy'
        self._fuzzy = fuzzy


class EWord(AbstractEItem):

    ADDITIONAL_KEYS_TO_ADD = ('value', )

    def __init__(self, value):
        super().__init__()
        self.value = value

    @property
    def json(self):
        if self.value == '*':
            return {"exists": {"field": self.field}}
        return super().json


class EPhrase(AbstractEItem):

    ADDITIONAL_KEYS_TO_ADD = ('query',)
    _proximity = None

    def __init__(self, phrase):
        super().__init__(method='match_phrase')
        self.query = re.search(r'"(?P<value>.+)"', phrase).group("value")

    @property
    def slop(self):
        return self._proximity

    @slop.setter
    def slop(self, slop):
        self._proximity = slop
        self.ADDITIONAL_KEYS_TO_ADD += ('slop', )


class ERange(AbstractEItem):

    def __init__(self, lt=None, lte=None, gt=None, gte=None):
        super().__init__(method='range')
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
