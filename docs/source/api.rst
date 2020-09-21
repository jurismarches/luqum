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

.. _elasticsearch-api:

Transforming to Elastic Search queries
======================================

luqum.schema
------------

.. autoclass:: luqum.elasticsearch.schema.SchemaAnalyzer
   :members: 
   :member-order: bysource


luqum.elasticsearch
--------------------

.. autoclass:: luqum.elasticsearch.visitor.ElasticsearchQueryBuilder
   :members: __init__, __call__
   :member-order: bysource


Utilities
==========


luqum.visitor: Manipulating trees
----------------------------------

.. automodule:: luqum.visitor
   :members:
   :member-order: bysource


luqum.naming: Naming query parts
---------------------------------

.. automodule:: luqum.naming
   :members:
   :member-order: bysource

luqum.auto_head_tail: Automatic addition of spaces
--------------------------------------------------

.. automodule:: luqum.auto_head_tail
   :members:

luqum.pretty: Pretty printing
------------------------------

.. automodule:: luqum.pretty
   :members:

luqum.check: Checking for validity
-----------------------------------

.. automodule:: luqum.check
   :members:

luqum.utils: Misc
-----------------

.. automodule:: luqum.utils
   :members:
   :member-order: bysource
