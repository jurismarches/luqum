API
#####

Parsing and constructing queries
==================================

This is the core of the library. A parser and the syntax tree definition.

luqum.parser
---------------

.. automodule:: luqum.parser
   :members: parser

luqum.tree
---------------

.. automodule:: luqum.tree
   :members:
   :member-order: bysource

Transforming to Elastic Search queries
======================================

luqum.elasticsearch
--------------------

.. autoclass:: luqum.elasticsearch.visitor.ElasticsearchQueryBuilder
   :members: __init__, __call__
   :member-order: bysource


Utilities
==========

luqum.utils
------------

.. automodule:: luqum.utils
   :members:
   :member-order: bysource

luqum.pretty
--------------

.. automodule:: luqum.pretty
   :members:

luqum.check
--------------

.. automodule:: luqum.check
   :members:
