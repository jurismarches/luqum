Quick start
===========

    >>> from unittest import TestCase
    >>> t = TestCase()
    >>> t.maxDiff = None


.. _tutorial-parsing:

Parsing
-------

.. py:currentmodule:: luqum.parser

To parse a query you need to import the :py:data:`parser`, and give it a string to parse::

    >>> from luqum.parser import parser
    >>> tree = parser.parse('(title:"foo bar" AND body:"quick fox") OR title:fox')

You'll get an object which is a tree, made of the elements composing the query::

    >>> print(repr(tree))
    OrOperation(Group(AndOperation(SearchField('title', Phrase('"foo bar"')), SearchField('body', Phrase('"quick fox"')))), SearchField('title', Word('fox')))

This can be viewed like that:

.. graphviz::

   digraph foo {
     or1 [label="OrOperation"];
     group1 [label="Group"];
     and1 [label="AndOperation"];
     search_title1 [label="SearchField\ntitle"];
     foo_bar [label="Phrase\nfoo bar"];
     search_body [label="SearchField\nbody"];
     quick_fox [label="Phrase\nquick fox"];
     search_title2 [label="SearchField\ntitle"];
     fox [label="Word\nfox"];
     or1 -> group1;
     or1 -> search_title2;
     group1 -> and1;
     and1 -> search_title1;
     and1 -> search_body;
     search_title1 -> foo_bar;
     search_body -> quick_fox;
     search_title2 -> fox;
   }


You can convert it back to a query using the standard ``str`` method from python::

    >>> print(str(tree))
    (title:"foo bar" AND body:"quick fox") OR title:fox

Manipulating
------------

One of the goal of luqum is to be able to manipulate queries.

In the previous request we can modify ``"foo bar"`` for ``"lazy dog"``::

    >>> tree.children[0].children[0].children[0].children[0].value = '"lazy dog"'
    >>> print(str(tree))
    (title:"lazy dog" AND body:"quick fox") OR title:fox

That was a bit tedious and also very specific to this tree.
Usually you will use recursion and visitor pattern to do such things.

.. py:currentmodule:: luqum.visitor

Luqum does provide some helpers like :py:class:`TreeTransformer` for this::

    >>> from luqum.visitor import TreeTransformer
    >>> class MyTransformer(TreeTransformer):
    ...     def visit_search_field(self, node, context):
    ...         if node.expr.value == '"lazy dog"':
    ...             new_node = node.clone_item()
    ...             new_node.expr = node.expr.clone_item(value = '"back to foo bar"')
    ...             yield new_node
    ...         else:
    ...             yield from self.generic_visit(node, context)
    ...
    >>> transformer = MyTransformer()
    >>> new_tree = transformer.visit(tree)
    >>> print(str(new_tree))
    (title:"back to foo bar" AND body:"quick fox") OR title:fox

.. _tutorial-elastic:

Transforming to elastic query
-----------------------------

Luqum also offers you to transform Lucene queries to `Elasticsearch queries DSL`_.

This is useful to extend capacities of Lucene queries and get the best out of elastic search.

The hard way
.............

To help interpret the requests,
we need to pass a list of fields to consider as terms (as opposed to full text searches).
We may also pass default operator, and default fields::

    >>> from luqum.elasticsearch import ElasticsearchQueryBuilder
    >>> es_builder = ElasticsearchQueryBuilder(not_analyzed_fields=["published", "tag"])

    >>> tree = parser.parse('''
    ...     title:("brown fox" AND quick AND NOT dog) AND
    ...     published:[* TO 1990-01-01T00:00:00.000Z] AND
    ...     tag:fable
    ...     ''')
    >>> query = es_builder(tree)
    >>> t.assertDictEqual(
    ...     query,
    ...     {'bool': {'must': [
    ...         {'bool': {'must': [
    ...             {'match_phrase': {'title': {'query': 'brown fox'}}},
    ...             {'match': {'title': {'query': 'quick', 'zero_terms_query': 'all'}}},
    ...             {'bool': {'must_not': [
    ...                 {'match': {'title': {'query': 'dog', 'zero_terms_query': 'none'}}}]}}]}},
    ...         {'range': {'published': {'lte': '1990-01-01T00:00:00.000Z'}}},
    ...         {'term': {'tag': {'value': 'fable'}}}]}})

You may also use nested fields or object fields::

    >>> es_builder = ElasticsearchQueryBuilder(
    ...     nested_fields={"authors": {"given_name", "last_name", "city"}},
    ...     object_fields=["authors.city.name"])
    >>> tree = parser.parse('''
    ...     title:"quick brown fox" AND
    ...     authors:(given_name:Ja* AND last_name:London AND city.name:"San Francisco")
    ...     ''')
    >>> query = es_builder(tree)
    >>> t.assertDictEqual(
    ...     query,
    ...     {'bool': {'must': [
    ...         {'match_phrase': {'title':
    ...              {'query': 'quick brown fox'}}},
    ...         {'nested': {
    ...             'query': {'bool': {'must': [
    ...                 {'query_string': {
    ...                     'default_field': 'authors.given_name',
    ...                     'analyze_wildcard': True,
    ...                     'query': 'Ja*',
    ...                     'allow_leading_wildcard': True}},
    ...                 {'match': {
    ...                     'authors.last_name': {
    ...                     'query': 'London',
    ...                     'zero_terms_query': 'all'}}},
    ...                 {'match_phrase': {'authors.city.name': {
    ...                     'query': 'San Francisco'}}}]}},
    ...             'path': 'authors'}}]}})

The easy way
.............

.. py:currentmodule:: luqum.elasticsearch.visitor

As the parameters to :py:class:`ElasticsearchQueryBuilder`
can be deduced from ElasticSearch schema,
we provide a tool to get them easily.
Just give your ES Index configuration
(that you have in you code, or that you ask to your ES instance),
and it computes parameters for you.

You got this schema::

    >>> from luqum.elasticsearch import SchemaAnalyzer
    >>> MESSAGES_SCHEMA = {
    ...     "settings": {"query": {"default_field": "message"}},
    ...     "mappings": {
    ...         "type1": {
    ...             "properties": {
    ...                 "message": { "type": "text" },
    ...                 "created": { "type": "date" },
    ...                 "author": {
    ...                     "type": "object",
    ...                     "properties": {
    ...                         "given_name": { "type": "keyword" },
    ...                         "last_name": { "type": "keyword" },
    ...                     },
    ...                 },
    ...                 "references": {
    ...                     "type": "nested",
    ...                     "properties": {
    ...                         "link_type": { "type": "keyword" },
    ...                         "link_url": {"type": "keyword"},
    ...                     },
    ...                 },
    ...             },
    ...         },
    ...     },
    ... }


.. py:currentmodule:: luqum.elasticsearch.schema

The schema analyzer (:py:class:`SchemaAnalyzer`)
makes it easy to get a query builder::

    >>> schema_analizer = SchemaAnalyzer(MESSAGES_SCHEMA)
    >>> message_es_builder = ElasticsearchQueryBuilder(**schema_analizer.query_builder_options())

That works::

    >>> q = 'message:"exciting news" AND author.given_name:John AND references.link_type:action'
    >>> tree = parser.parse(q)
    >>> query = message_es_builder(tree)
    >>> t.assertDictEqual(
    ...     query,
    ...     {'bool': {'must': [
    ...         {'match_phrase': {'message':
    ...             {'query': 'exciting news'}}},
    ...         {'term': {'author.given_name': {'value': 'John'}}},
    ...         {'nested':
    ...             {'path': 'references',
    ...              'query': {'term': {'references.link_type': {'value': 'action'}}},
    ...             },
    ...         },
    ...     ]}}
    ... )


You can use this JSON directly with `elasticsearch python bindings`_,
but also use it to build a query with `elasticsearch_dsl`_.

.. note::
   There are some limitations to this transformation.
   Please, refers to the API :ref:`elasticsearch-api`


Note that under the hood, the operation is two fold:
it first create a new specific tree from the luqum tree.
This tree is then capable of giving it's JSON like representation
(that is JSON compatible python objects).

Modifying the generated queries
...............................

The JSON representation is built using elements (``EWord``,
``EPhrase``, ``EBoolOperation``, ...).

An easy way to modify the generated queries DSL, is to inherit
:py:class:`ElasticsearchQueryBuilder` and modify the behavior of
these ``E-elements``. You can do that by replacing each element
using the attributes defined as follow::

    >>> class ElasticsearchQueryBuilder(TreeVisitor):
    ... [...]
    ... E_MUST = EMust
    ... E_MUST_NOT = EMustNot
    ... E_SHOULD = EShould
    ... E_WORD = EWord
    ... E_PHRASE = EPhrase
    ... E_RANGE = ERange
    ... E_NESTED = ENested
    ... E_BOOL_OPERATION = EBoolOperation

For instance, if you want your query to use ``match`` instead of
``term`` for words::

    >>> from luqum.elasticsearch.visitor import EWord, ElasticsearchQueryBuilder
    >>> from luqum.tree import AndOperation

    >>> class EWordMatch(EWord):
    ...     @property
    ...     def json(self):
    ...          if self.q == '*':
    ...              return super().json
    ...          return {"match": {self.field: self.q}}

    >>> class MyElasticsearchQueryBuilder(ElasticsearchQueryBuilder):
    ...     E_WORD = EWordMatch
    ...

    >>> transformer = MyElasticsearchQueryBuilder()
    >>> q = 'message:* AND author:John AND link_type:action'
    >>> tree = parser.parse(q)
    >>> query = transformer(tree)
    >>> t.assertDictEqual(
    ...     query,
    ...     {'bool': {'must': [
    ...         {'exists': {'field': 'message'}},
    ...         {'match': {'author': 'John'}},
    ...         {'match': {'link_type': 'action'}}]}}


.. _tutorial-unknown-operation:


The unknown operation
----------------------


.. py:currentmodule:: luqum.tree

In query you may use an implicit operator
leaving a blank between two expressions instead of OR or AND.
Because the meaning of this operator is unknown at parsing time,
it is replaced by a special :py:class:`UnknownOperation` operation.

::

    >>> tree = parser.parse('foo bar')
    >>> tree
    UnknownOperation(Word('foo'), Word('bar'))

To help you deal with this we provide a transformer,
that will smartly replace ``UnkownOperation`` by ``AndOperation`` or ``OrOperation``.

    >>> from luqum.utils import UnknownOperationResolver
    >>> resolver = UnknownOperationResolver()
    >>> str(resolver(tree))
    'foo AND bar'

.. _tutorial-pretty-printing:

Head and tail
--------------

In an expression there may be different spaces, or other characters
as delimiter between sub expressions.

Most of the time, as we manipulate expressions we may want to keep those spaces,
as they may be meaningful to their author (for example formating the expression).

Luqum manage this by computing a `head` and `tail` on each element
that gives the characters before and after the part of the expression the item represents.

Those properties are computed at parsing time.
If you build trees computationaly (or change them), you will have to set them yourself.

For example, do not write::

    >>> from luqum.tree import AndOperation, Word
    >>> my_tree =  AndOperation(Word('foo'), Word('bar'))

As it would result in::

    >>> print(my_tree)
    fooANDbar

Instead, you may write:

    >>> my_tree =  AndOperation(Word('foo', tail=" "), Word('bar', head=" "))
    >>> print(my_tree)
    foo AND bar

.. py:currentmodule:: luqum.auto_head_tail

Although luqum provides a util :py:func:`auto_head_tail`
to quickly add minimal head / tail where needed::

    >>> from luqum.tree import Not
    >>> from luqum.auto_head_tail import auto_head_tail
    >>> my_tree =  AndOperation(Word('foo'), Not(Word('bar')))
    >>> my_tree = auto_head_tail(my_tree)
    >>> print(my_tree)
    foo AND NOT bar


Pretty printing
---------------

.. py:currentmodule:: luqum

Luqum also comes with a query pretty printer in :py:mod:`pretty`.

Say we got an expression::

  >>> from luqum.pretty import prettify
  >>> tree = parser.parse(
  ...     'some_long_field:("some long value" OR "another quite long expression"~2 OR "even something more expanded"^4) AND yet_another_fieldname:[a_strange_value TO z]')

We can pretty print it::

  >>> print(prettify(tree))
  some_long_field: (
      "some long value"
      OR
      "another quite long expression"~2
      OR
      "even something more expanded"^4
  )
  AND
  yet_another_fieldname: [a_strange_value TO z]


.. _`elasticsearch python bindings`: https://pypi.python.org/pypi/elasticsearch/
.. _`elasticsearch_dsl`: https://pypi.python.org/pypi/elasticsearch-dsl
.. _`Elasticsearch queries DSL`: https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl.html

Named Queries: explaining a match
---------------------------------

.. py:currentmodule:: luqum.naming

Luqum support using named queries.
The main purpose would be to highlight to the user the matching parts of his query.

Say we have a query::

   >>> expr = "foo~2 OR (bar AND baz)"
   >>> tree = parser.parse(expr)

We can use :py:func:`auto_name` to automatically add names::

   >>> from luqum.naming import auto_name
   >>> names = auto_name(tree)

names contains a dict association names to path in the luqum tree.
For example the first name "a" is associated with element "foo",
and we can retrieve it easily thanks to small utils for navigating the tree::

   >>> from luqum.naming import element_from_path, element_from_name
   >>> element_from_name(tree, "a", names)
   Fuzzy(Word('foo'), 2)
   >>> element_from_path(tree, (0, 0))
   Word('foo')


The generated elastic search queries use the names
when  building the query (see `elastic named queries`__)::

   >>> es_query = es_builder(tree)
   >>> t.assertDictEqual(
   ...     es_query,
   ...     {'bool': {'should': [
   ...         {'fuzzy': {'text': {'fuzziness': 2.0, 'value': 'foo', '_name': 'a'}}},
   ...         {'bool': {'must': [
   ...             {'match': {'text': {'query': 'bar', 'zero_terms_query': 'all', '_name': 'c'}}},
   ...             {'match': {'text': {'query': 'baz', 'zero_terms_query': 'all', '_name': 'd'}}}
   ...         ]}}
   ...     ]}}
   ... )

If you use this on elasticsearch, for each record,
elastic will return the part of the queries matched by the record, using their names.

Imagine elasticsearch returned us we match on 'b' and 'c'::

   >>> matched_queries = ['b', 'c']

To display it to the user, we have two step to undergo:
first identifying every matching element using :py:class:`MatchingPropagator`::

   >>> from luqum.naming import MatchingPropagator, matching_from_names
   >>> propagate_matching = MatchingPropagator()
   >>> paths_ok, paths_ko = propagate_matching(tree, *matching_from_names(matched_queries, names))

And then using :py:class:`HTMLMarker` to display it in html (you could make your own also)::

   >>> from luqum.naming import HTMLMarker
   >>> mark_html = HTMLMarker()  # you can customize some parameters, refer to doc
   >>> mark_html(tree, paths_ok, paths_ko)
   '<span class="ok"><span class="ko">foo~2 </span>OR (<span class="ko"><span class="ok">bar </span>AND baz</span>)</span>'


__ https://www.elastic.co/guide/en/elasticsearch/reference/current/search-request-body.html#request-body-search-queries-and-filters
