luqum - A lucene query parser in Python, using PLY
#########################################################

|readthedocs| |travis| |coveralls|

|logo| 

"luqum" (as in LUcene QUery Manipolator) is a tool to parse queries 
written in the `Lucene Query DSL`_ and build an abstract syntax tree 
to inspect, analyze or otherwise manipulate search queries.

Compatible with Python 3.3 & 3.4.

Installation
------------

``pip install luqum``


Dependencies
------------

PLY==3.8


Full documentation
------------------

http://luqum.readthedocs.org/en/latest/

Quick Start
-----------

.. code-block:: python

    >>> from luqum.parser import parser
    >>> tree = parser.parse('(title:"foo bar" AND body:"quick fox") OR title:fox')
    # See the syntax tree
    >>> repr(tree)
    OrOperation(Group(AndOperation(SearchField(Phrase("foo bar")), SearchField(Phrase("quick fox")))), SearchField(Word(fox)))
    # Convert that tree back to a search string
    >>> str(tree)
    (title:"foo bar" AND body:"quick fox") OR title:fox'

    # Transform a query by manipulating the syntax tree
    >>> tree = parser.parse('foo:bar')
    >>> tree.name = 'wat'
    >>> tree.expr.value = 'woot'
    >>> str(tree)
    'wat:woot'


.. _`Lucene Query DSL` : https://lucene.apache.org/core/3_6_0/queryparsersyntax.html

.. |logo| image:: https://raw.githubusercontent.com/jurismarches/luqum/master/luqum-logo.png

.. |travis| image:: http://img.shields.io/travis/jurismarches/luqum/master.svg?style=flat
    :target: https://travis-ci.org/jurismarches/luqum
.. |coveralls| image:: http://img.shields.io/coveralls/jurismarches/luqum/master.svg?style=flat
    :target: https://coveralls.io/r/jurismarches/luqum
.. |readthedocs| image:: https://readthedocs.org/projects/luqum/badge/?version=latest
    :target: http://luqum.readthedocs.org/en/latest/?badge=latest
    :alt: Documentation Status
