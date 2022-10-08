import abc
import re

from ..tree import Term


class JsonSerializableMixin:
    """
    Mixin to force subclasses to implement the json method
    """

    @property
    @abc.abstractmethod
    def json(self):
        pass  # pragma: no cover


class AbstractEItem(JsonSerializableMixin):
    """
    Base item element to build the "item" json
    For instance : {"term": {"field": {"value": "query"}}}
    """

    boost = None
    _fuzzy = None

    _KEYS_TO_ADD = ('boost', 'fuzziness', '_name')
    ADDITIONAL_KEYS_TO_ADD = ()

    def __init__(self, no_analyze=None, method='term', fields=[], _name=None, field_options=None):
        self._method = method
        self._fields = fields
        self._no_analyze = no_analyze if no_analyze else []
        self.zero_terms_query = 'none'
        self.field_options = field_options or {}
        if _name is not None:
            self._name = _name

    @property
    def json(self):
        field = self.field
        inner_json = dict(self.field_options.get(field, {}))
        result = inner_json.pop('match_type', None)  # remove "match_type" key
        if not result:  # conditionally remove "type" (for backward compatibility)
            inner_json.pop('type', None)
        if self.method in ['query_string', 'multi_match']:
            json = {self.method: inner_json}
        else:
            json = {self.method: {field: inner_json}}

        # add base conf
        keys = self._KEYS_TO_ADD + self.ADDITIONAL_KEYS_TO_ADD
        for key in keys:
            value = getattr(self, key, None)
            if value is not None:
                if key == 'q':
                    if 'match' in self.method:
                        inner_json['query'] = value
                        if self.method == 'match':
                            inner_json['zero_terms_query'] = self.zero_terms_query
                    elif self.method == 'query_string':
                        inner_json['query'] = value
                        inner_json['default_field'] = self.field
                        inner_json['analyze_wildcard'] = inner_json.get('analyze_wildcard', True)
                        inner_json['allow_leading_wildcard'] = inner_json.get(
                            'allow_leading_wildcard', True)
                    else:
                        inner_json['value'] = value
                else:
                    inner_json[key] = value
        return json

    @property
    def field(self):
        return '.'.join(self._fields)

    @property
    def fuzziness(self):
        return self._fuzzy

    @fuzziness.setter
    def fuzziness(self, fuzzy):
        self._method = 'fuzzy'
        self._fuzzy = fuzzy

    def _value_has_wildcard_char(self):
        # reuse the work done in Term
        term = Term(getattr(self, 'q', ''))
        return term.has_wildcard()

    def _is_analyzed(self):
        return self.field not in self._no_analyze

    @property
    def method(self):
        is_analyzed = self._is_analyzed()
        if not is_analyzed and self._value_has_wildcard_char():
            return 'wildcard'
        elif is_analyzed:
            if self._value_has_wildcard_char():
                return 'query_string'
            elif self._method.startswith("match"):
                options = self.field_options.get(self.field, {})
                # Support the type opiton for backward compatibility
                return options.get("match_type", options.get("type", self._method))
        return self._method


class EWord(AbstractEItem):
    """
    Build a word

    ::
        >>> from unittest import TestCase
        >>> TestCase().assertDictEqual(
        ...     EWord(q='test', fields=["text"]).json,
        ...     {'term': {'text': {
        ...         'value': 'test'
        ...     }}},
        ... )
    """

    ADDITIONAL_KEYS_TO_ADD = ('q', )

    def __init__(self, q, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.q = q

    @property
    def json(self):
        # field:* is transformed to exists query
        if self.q == '*':
            query = {"exists": {"field": self.field}}
            name = getattr(self, "_name", None)
            if name is not None:
                query["exists"]["_name"] = name
            return query
        return super().json


class EPhrase(AbstractEItem):
    """
    Build a phrase

    ::
        >>> from unittest import TestCase
        >>> TestCase().assertDictEqual(
        ...     EPhrase(phrase='"another test"', fields=["text"]).json,
        ...     {'match_phrase': {'text': {'query': 'another test'}}},
        ... )
    """

    ADDITIONAL_KEYS_TO_ADD = ('q',)
    _proximity = None

    def __init__(self, phrase, *args, **kwargs):
        super().__init__(method='match_phrase', *args, **kwargs)
        phrase = self._replace_CR_and_LF_by_a_whitespace(phrase)
        self.q = self._remove_double_quotes(phrase)

    def __repr__(self):
        return "%s(%s=%s)" % (self.__class__.__name__, self.field, self.q)

    def _replace_CR_and_LF_by_a_whitespace(self, phrase):
        return re.sub(r'\s+', ' ', phrase)

    def _remove_double_quotes(self, phrase):
        return phrase[1:-1]

    def _value_has_wildcard_char(self):
        # Wildcard not active in Phrase
        return False

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
    ::

        >>> from unittest import TestCase
        >>> TestCase().assertDictEqual(
        ...     ERange(lt=100, gte=10, fields=["text"]).json,
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
    pass


class EOperation(AbstractEOperation):
    """
    Abstract operation taking care of the json build
    """

    def __init__(self, items, **options):
        self.items = items
        self._method = None
        self.options = options

    def __repr__(self):
        items = ", ".join(i.__repr__() for i in self.items)
        return "%s(%s)" % (self.__class__.__name__, items)

    @property
    def json(self):
        bool_query = {self.operation: [item.json for item in self.items]}
        query = dict(bool_query, **self.options)
        return {'bool': query}


class ENested(AbstractEOperation):
    """
    Build ENested element

    Take care to remove ENested children
    """

    def __init__(self, nested_path, nested_fields, items, *args, _name=None, **kwargs):

        self._nested_path = [nested_path]
        self.items = self._exclude_nested_children(items)
        self._name = _name

    @property
    def nested_path(self):
        return '.'.join(self._nested_path)

    def __repr__(self):
        return "%s(%s, %s)" % (self.__class__.__name__, self.nested_path, self.items)

    def _exclude_nested_children(self, subtree):
        """
        Rebuild tree excluding ENested in children if some are present

        ::
            >>> from unittest import TestCase
            >>> tree = EMust(items=[
            ...     ENested(
            ...         nested_path='a',
            ...         nested_fields=['a'],
            ...         items=EPhrase('"François"', fields=["text"])
            ...     ),
            ...     ENested(
            ...         nested_path='a',
            ...         nested_fields=['a'],
            ...         items=EPhrase('"Dupont"', fields=["text"]))
            ... ])
            >>> nested_node = ENested(
            ...     nested_path='a', nested_fields=['a'], items=tree)
            >>> TestCase().assertEqual(
            ...     nested_node.__repr__(),
            ...     'ENested(a, EMust(EPhrase(text=François), EPhrase(text=Dupont)))'
            ... )
        """
        if isinstance(subtree, ENested):
            # Exclude ENested

            if subtree.nested_path == self.nested_path:
                return self._exclude_nested_children(subtree.items)
            else:
                return subtree
        elif isinstance(subtree, AbstractEOperation):
            # Exclude ENested in children
            subtree.items = [
                self._exclude_nested_children(child)
                for child in subtree.items
            ]
            return subtree
        else:
            # return the subtree once ENested has been excluded
            return subtree

    @property
    def json(self):
        data = {'nested': {'path': self.nested_path, 'query': self.items.json}}
        if self._name:
            data['nested']['_name'] = self._name
        return data


class EShould(EOperation):
    """
    Build a should operation

    ::
        >>> from unittest import TestCase
        >>> json = EShould(
        ...     items=[EPhrase('"monty python"', fields=["text"]),
        ...            EPhrase('"spam eggs"', fields=["text"])]
        ... ).json
        >>> TestCase().assertDictEqual(
        ...     json,
        ...     {'bool': {'should': [
        ...         {'match_phrase': {'text':
        ...             {'query': 'monty python'}}},
        ...         {'match_phrase': {'text': {'query': 'spam eggs'}}},
        ...     ]}}
        ... )
    """
    operation = 'should'


class AbstractEMustOperation(EOperation):

    def __init__(self, items, **options):
        op = super().__init__(items, **options)
        for item in self.items:
            item.zero_terms_query = self.zero_terms_query
        return op


class EMust(AbstractEMustOperation):
    """
    Build a must operation

    ::
        >>> from unittest import TestCase
        >>> json = EMust(
        ...     items=[EPhrase('"monty python"', fields=["text"]),
        ...            EPhrase('"spam eggs"', fields=["text"])]
        ... ).json
        >>> TestCase().assertDictEqual(
        ...     json,
        ...     {'bool': {'must': [
        ...         {'match_phrase': {'text':
        ...             {'query': 'monty python'}}},
        ...         {'match_phrase': {'text':
        ...             {'query': 'spam eggs'}}},
        ...     ]}}
        ... )
    """
    zero_terms_query = 'all'
    operation = 'must'


class EMustNot(AbstractEMustOperation):
    """
    Build a must not operation

    ::
        >>> from unittest import TestCase
        >>> TestCase().assertDictEqual(
        ...     EMustNot(items=[EPhrase('"monty python"', fields=["text"])],).json,
        ...     {'bool': {'must_not': [
        ...         {'match_phrase': {'text':
        ...             {'query': 'monty python'}}},
        ...     ]}}
        ... )
    """
    zero_terms_query = 'none'
    operation = 'must_not'


class EBoolOperation(EOperation):

    @property
    def json(self):
        must_items = []
        should_items = []
        must_not_items = []
        for item in self.items:
            if isinstance(item, EMust):
                must_items.extend(item.items)
            elif isinstance(item, EMustNot):
                must_not_items.extend(item.items)
            else:
                should_items.append(item)
        bool_query = {}
        if must_items:
            bool_query["must"] = [item.json for item in must_items]
        if should_items:
            bool_query["should"] = [item.json for item in should_items]
        if must_not_items:
            bool_query["must_not"] = [item.json for item in must_not_items]

        query = dict(bool_query, **self.options)
        return {'bool': query}


class ElasticSearchItemFactory:
    """
    Factory to preconfigure EItems and EOperation

    ::
        >>> from unittest import TestCase
        >>> factory = ElasticSearchItemFactory(
        ...     no_analyze=['text'], nested_fields=[], field_options={"text": {"slop": 1}})
        >>> word = factory.build(EWord, q='test', fields=["text"])
        >>> TestCase().assertDictEqual(
        ...     word.json,
        ...     {'term': {'text': {'value': 'test', "slop": 1}}},
        ... )
    """

    def __init__(self, no_analyze, nested_fields, field_options):
        self._no_analyze = no_analyze
        self._nested_fields = nested_fields
        self._nested_fields = nested_fields
        self._field_options = field_options

    def build(self, cls, *args, **kwargs):
        # add parameters based on item type
        if issubclass(cls, AbstractEItem):
            # eventually add field defaults to kwargs
            if "field_options" not in kwargs:
                kwargs = dict(kwargs, field_options=self._field_options)
            return cls(
                no_analyze=self._no_analyze,
                *args,
                **kwargs
            )
        elif cls is ENested:
            return cls(
                nested_fields=self._nested_fields,
                *args,
                **kwargs
            )
        else:
            return cls(*args, **kwargs)
