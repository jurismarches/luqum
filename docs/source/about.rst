What is Luqum
###############

Luqum stands for LUcene QUery Manipolator.

It features a python library with a parser for  the `Lucene Query DSL`_ as found in
`Solr`_ `query syntax`_ or
`ElasticSearch`_ `query string`_

From the parser it builds a tree.

This tree can eventually be manipulated and then transformed back into a query string.

You may use this to:

* make some sanity check on query
* make your own check on query (eg. forbid certain fields)
* replace some expressions in query
* pretty print a query
* inject queries in queries

The parser is built using `PLY`_.

.. warning::

   This library is not yet production ready.
   It also lacks some features.
   Contributions are welcome.

.. _`Lucene Query DSL`: https://lucene.apache.org/core/3_6_0/queryparsersyntax.html
.. _`Solr`: http://lucene.apache.org/solr/
.. _`query syntax`: https://wiki.apache.org/solr/SolrQuerySyntax
.. _`ElasticSearch`: https://www.elastic.co/products/elasticsearch
.. _`query string`: https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-query-string-query.html
.. _`PLY`: http://www.dabeaz.com/ply/ply.html
