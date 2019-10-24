luqum - A lucene query parser in Python, using PLY
#########################################################

|pypi-version| |readthedocs| |travis| |coveralls|

|logo| 

"luqum" (as in LUcene QUery Manipolator) is a tool to parse queries 
written in the `Lucene Query DSL`_ and build an abstract syntax tree 
to inspect, analyze or otherwise manipulate search queries.

It enables enriching the Lucene Query DSL meanings
(for example to support nested object searches or have particular treatments on some fields),
and transform lucene DSL queries to native `ElasticSearch JSON DSL`_

Thanks to luqum, your users may continue to write queries like:
`author.last_name:Smith OR author:(age:[25 TO 34] AND first_name:John)`
and you will be able to leverage ElasticSearch query DSL,
and control the precise meaning of each search terms.

Luqum is dual licensed under Apache2.0 and LGPLv3.

Compatible with Python 3.4+

Installation
============

``pip install luqum``


Dependencies
============

`PLY`_ >= 3.11


Full documentation
==================

http://luqum.readthedocs.org/en/latest/


.. _`Lucene Query DSL` : https://lucene.apache.org/core/3_6_0/queryparsersyntax.html
.. _`ElasticSearch JSON DSL`: https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl.html

.. _`PLY`: http://www.dabeaz.com/ply/

.. |logo| image:: https://raw.githubusercontent.com/jurismarches/luqum/master/luqum-logo.png

.. |pypi-version| image:: https://img.shields.io/pypi/v/luqum.svg
    :target: https://pypi.python.org/pypi/luqum
    :alt: Latest PyPI version
.. |travis| image:: http://img.shields.io/travis/jurismarches/luqum/master.svg?style=flat
    :target: https://travis-ci.org/jurismarches/luqum
.. |coveralls| image:: http://img.shields.io/coveralls/jurismarches/luqum/master.svg?style=flat
    :target: https://coveralls.io/r/jurismarches/luqum
.. |readthedocs| image:: https://readthedocs.org/projects/luqum/badge/?version=latest
    :target: http://luqum.readthedocs.org/en/latest/?badge=latest
    :alt: Documentation Status


