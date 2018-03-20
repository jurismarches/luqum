Changelog for luqum
###################

The format is based on `Keep a Changelog`_
and this project tries to adhere to `Semantic Versioning`_.

.. _`Keep a Changelog`: http://keepachangelog.com/en/1.0.0/
.. _`Semantic Versioning`_ http://semver.org/spec/v2.0.0.html

0.7.0 - 2018-03-20
==================

Added
-----

- Support for named queries (see `elastic named queries`__)
- Helper to automatically create ElasticSearch query builder options from the index configuration,
  see: :py:mod:`luqum.elasticsearch.schema`
- a new arg `field_options` on :py:class:`luqum.elasticsearch.visitor.ElasticsearchQueryBuilder`
  allows to add parameters to field queries.
  It also permits to control the type of query for match queries.

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
