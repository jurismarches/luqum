Changelog for luqum
###################

The format is based on `Keep a Changelog`_
and this project tries to adhere to `Semantic Versioning`_.

.. _`Keep a Changelog`: http://keepachangelog.com/en/1.0.0/
.. _`Semantic Versioning`: http://semver.org/spec/v2.0.0.html

0.11.0 - 2021-01-06
===================

Changed
-------

- completely modified the naming module and `auto_name` function, as it was not practical as is.

Added
-----

- added tools to build visual explanations about why a request matches a results
  (leveraging `elasticsearch named queries`__.
- added a visitor and transformer that tracks path to element while visiting the tree.

__ https://www.elastic.co/guide/en/elasticsearch/reference/current/search-request-body.html#request-body-search-queries-and-filters

Fixed
-----

- fixed the handling of names when transforming luqum tree to elasticsearch queries
  and added integration tests.


0.10.0 - 2020-09-22
===================

Added
-----

- support for parsing Regular expressions like `/foo/` (no transformation to Elasticsearch DSL yet)
- basic support for head and tail of expressions (the separators) 
  and for their position (pos and size) in original text
- added `auto_head_tail` util
  (use it if you build your tree programatically and want a printable representation)
- tree item now support a `clone_item` method and a setter for children.
  This should help with making transformation pattern easier.
- New `visitor.TreeVisitor` and `visitor.TreeTransformer` classes to help in processing trees
  `utils.LuceneTreeVisitor`, `utils.LuceneTreeVisitorV2` and `utils.LuceneTreeTransformer`
  are warned as deprecated (but still works).

Changed
-------

- support for python 3.8 added, support for python 3.4 and 3.5 dropped
- better printing of Proximity and Fuzzy items (preserve implicit nature of degree)
- raise `IllegalCharacterError` on illegal character found instead of printing and skipping
- renamed `ParseError` to `ParseSyntaxError`, and kept `ParseError` as a parent exception

Fixed
-----

- Range item were not checking for bounds type on equality
- Boost item were not checking for force on equality
- Reorganize tests

0.9.0 - 2020-07-29
==================

Added
-----

- support for elasticsearch 7

0.8.1 - 2019-11-01
==================

Added
-----

- added Apache 2 license, while maintaining LGPLv3+

0.8.0 - 2019-08-02
==================

Added
-----

- support for `multi_match` query in `ElasticsearchQueryBuilder`.

Fixed
-----

- SchemaAnalyzer, should count non text fields as not_analyzed
- `ElasticsearchQueryBuilder`'s `field_options` parameter
  can accept `match_type` instead of `type` to change request type.
  This is now the prefered way over `type`
  which may more easily conflict with request parameters.

0.7.5 - 2018-10-29
==================

Added
-----

- handling sub fields (aka `multi-fields`__)

__ https://www.elastic.co/guide/en/elasticsearch/reference/6.3/multi-fields.html

Fixed
-----

- fixed bug on equality, having more children in one tree than in the other,
  was not triggering inequality if first nodes were the same !

0.7.4 - 2018-08-28
==================

Added
-----

- handling `special characters escaping`_
- added `iter_wildcards` and `split_wildcards` to have a finer grained search of wildcard in terms

.. _`special characters escaping`: https://lucene.apache.org/core/3_6_0/queryparsersyntax.html#Escaping%20Special%20Characters

Fixed
-----

- fixed bug in `luqum.utils.LuceneTreeTransformer` when removing node
- fixed bug in handling approx operator on multiple words in
  `luqum.elasticsearch.visitor.ElasticsearchQueryBuilder`
- test coverage now check branch

0.7.3 - 2018-06-08
===================

Fixed
-----

- On ElasticSearch query transformation, Luqum was interpreting wildcards in Phrases where as it should not

0.7.2 - 2018-05-14
===================

Fixed
-----

- adding the `zero_terms_query` to `match_phrase` was a mistake (introduced in 0.7.0).

Added
-----

- 0.7.0 introduced the `match` query for queries with single words on analyzed fields,
  whereas before it was using `match_phrase`.
  Although this is more coherent,
  this may cause difficulties on edge cases
  as this may leads to results different from previous release.

  This behaviour might be disabled using a new `match_word_as_phrase` parameter
  to `luqum.elasticsearch.visitor.ElasticsearchQueryBuilder`.
  Note that this parameter maybe removed in future release.
  (the `field_options` might be used instead on a per field basis).


0.7.1 - 2018-03-20
==================

Fixed
-----

- version introduced because of a bad upload on pypi (Restructured description error)

0.7.0 - 2018-03-20
==================

Added
-----

- Support for named queries (see `elastic named queries`__)
- Helper to automatically create ElasticSearch query builder options from the index configuration,
  see: `luqum.elasticsearch.schema`
- a new arg `field_options` on `luqum.elasticsearch.visitor.ElasticsearchQueryBuilder`
  allows to add parameters to field queries.
  It also permits to control the type of query for match queries.
- now for a query with a single word, if the field is analyzed,
  the transformation to elastic search query will use a "match" query instead of a "match_phrase".
  This is more conform in behaviour to what the expression of "query_string" would produce.


Fixed
-----

- small fix in utils.TreeTransformerV2,
  which was not removing elements from lists or tuple as stated
- single word matches, are now `match`, and not `match_phrase`
- `match_phrase` has the `zero_terms_query` field, as for `match`

__ https://www.elastic.co/guide/en/elasticsearch/reference/current/search-request-named-queries-and-filters.html

Changed
--------

- dropped official Python 3.3 support

0.6.0 - 2017-12-12
==================

Added
-----

- Manage object fields in elasicsearch transformation

Fixed
-----

- minor fix, getting better error message when parsing error is at the end of content

Changed
--------

- better handling of nested fields may lead to shorter requests

0.5.3 - 2017-08-21
==================

Added
-----

- A class to transform smartly replace implicit operations with explicit one (*OR* or *AND*)

Fixed
-----

- handling of fields names with numbers followed by a number
  (better handling of time in expressions)

Changed
-------

- now using ply 3.10

0.5.2 - 2017-05-29
==================

Changed
-------

- better recursion in the tree transformer util (API Change)

Fixed
-----

- handling of empty phrases for elasticsearch query builder

0.5.1 - 2017-04-10
==================

a minor release

Changed
-------

- Better handling of the implicit operator on printing

0.5.0 - 2017-04-04
==================

Changed
-------

- Operations are now supporting multiple operands (instead of only two).
  This mitigate the construction of very deep trees.

Fixed
-----

- fixes and improvement of documentation

0.4.0 - 2016-12-05
==================

Changed
-------

- The Lucene query checker now checks nested fields before transformation to prevent bad usage

0.3.1 - 2016-11-23
==================

Added
-----

- Support for nested fields in Elastic Search queries

Changed
-------

- improved performances by adding a cache to the tree visitor utility

0.3 - 2016-11-21
=================

(Note that 0.2 version was skipped)

Added
-----

- Transforming Lucene queries to Elastic Search queries
- Added a new tree visitor `TreeVisitorV2` more easy to use

Fixed
-----
- Improved first tree visitor utility and its tests (API Change)


0.1 - 2016-05-17
=================

This was the initial release of Luqum.

Added
------

- the parser and the tree structure
- the visitor and transformer utils
- the Lucene query consistency checker
- the prettify for pretty printing
