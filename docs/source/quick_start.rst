Quick start
===========

    >>> from unittest import TestCase
    >>> t = TestCase()


.. _tutorial-parsing:

Parsing
-------

To parse a query you need to import the parser, and give it a string to parse::

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

That was a bit tedious. Of course, normally you will use recursion and visitor pattern
to do such things.

Luqum does provide some helpers for this::

    >>> from luqum.utils import LuceneTreeTransformer
    >>> class MyTransformer(LuceneTreeTransformer):
    ...     def visit_search_field(self, node, parents):
    ...         if node.expr.value == '"lazy dog"':
    ...             node.expr.value = '"back to foo bar"'
    ...         return node
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
   ...             {'match': {'title': {'query': 'quick',
   ...                                  'type': 'phrase',
   ...                                  'zero_terms_query': 'all'}}},
   ...             {'bool': {'must_not': [{'match': {'title': {'query': 'dog',
   ...                                                         'type': 'phrase',
   ...                                                         'zero_terms_query': 'none'}}}]}}]}},
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
   ...         {'match_phrase': {'title': {'query': 'quick brown fox'}}},
   ...         {'nested': {
   ...             'query': {'bool': {'must': [
   ...                 {'query_string': {
   ...                     'default_field': 'authors.given_name',
   ...                     'analyze_wildcard': True,
   ...                     'query': 'Ja*',
   ...                     'allow_leading_wildcard': True}},
   ...                 {'match': {'authors.last_name': {
   ...                     'query': 'London',
   ...                     'type': 'phrase',
   ...                     'zero_terms_query': 'all'}}},
   ...                 {'match_phrase': {'authors.city.name': {
   ...                     'query': 'San Francisco'}}}]}},
   ...             'path': 'authors'}}]}})

You can use this JSON directly with `elasticsearch python bindings`_,
but also use it to build a query with `elasticsearch_dsl`_.

.. note::
   The list of terms fields could, of course,
   be automatically deduced from the elasticsearch schema

   Also there are some limitations to this transformation.
   Please, refers to the API :ref:`elasticsearch-api`
   

Note that under the hood, the operation is too fold:
it first create a new specific tree from the luqum tree.
This tree is then capable of giving it's JSON like represetation
(that is JSON compatible python objects).

.. _tutorial-unknown-operation:


The unknown operation
----------------------

In query you may use an implicit operator
leaving a blank between two expressions instead of OR or AND.
Because the meaning of this operator is unknown at parsing time,
it is replaced by a special ``UnknownOperation`` operation.

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

Pretty printing
---------------

Luqum also comes with a query pretty printer.

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

Named Queries
--------------

Luqum support using named queries.
The main purpose would be to highlight to the user the matching parts of his query.

Say we have a query::

   >>> expr = "foo~2 OR (bar AND baz)"
   >>> tree = parser.parse(expr)

We can use :py:func:`luqum.naming.auto_name` to automatically add names::

   >>> from luqum.naming import auto_name
   >>> auto_name(tree)

The generated elastic search queries use the names
when  building the query (see `elastic named queries`__)::

   >>> es_query = es_builder(tree)
   >>> t.assertDictEqual(
   ...     es_query,
   ...     {'bool': {'should': [
   ...         {'fuzzy': {'text': {'_name': '0_0', 'fuzziness': 2.0, 'value': 'foo'}}},
   ...         {'bool': {'must': [
   ...             {'match': {'text': {
   ...                 '_name': '0_1_0',
   ...                 'query': 'bar', 'type': 'phrase', 'zero_terms_query': 'all'}}},
   ...             {'match': {'text': {
   ...                 '_name': '0_1_1',
   ...                 'query': 'baz', 'type': 'phrase', 'zero_terms_query': 'all'}}}
   ...         ]}}
   ...     ]}}
   ... )

If you use this on elasticsearch, for each record,
elastic will return the part of the queries matched by the record, using their names.

To display it to the user, we can find back which name refers to which  part of the query,
using :py:func:`luqum.naming.name_index`::

   >>> from luqum.naming import name_index, extract
   >>> index = name_index(tree)
   >>> index["0_1_0"]  # for each name, associate start index and length
   (10, 3)
   >>> extract(expr, "0_1_0", index)
   'bar'
   >>> extract(expr, "0_1", index)
   'bar AND baz'
   
   

__ https://www.elastic.co/guide/en/elasticsearch/reference/current/search-request-named-queries-and-filters.html
