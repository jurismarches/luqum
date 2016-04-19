Quick start
===========

To parse a query you need to import the parser, and give it a string to parse::

    >>> from luqum.parser import parser
    >>> tree = parser.parse('(title:"foo bar" AND body:"quick fox") OR title:fox')

You'll get an object wich is a tree, made of the elements composing the query::

    >>> print(repr(tree))
    OrOperation(Group(AndOperation(SearchField('title', Phrase('"foo bar"')), SearchField('body', Phrase('"quick fox"')))), SearchField('title', Word('fox')))


You can convert it back to a query using the standard ``str`` method from python::

    >>> print(str(tree))
    (title:"foo bar" AND body:"quick fox") OR title:fox

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


Luqum also comes with a query pretty printer::

  >>> from luqum.pretty import prettify
  >>> tree = parser.parse(
  ...     'some_long_field:("some long value" OR "another quite long expression"~2 OR "even something more expanded"^4) AND yet_another_fieldname:[a_strange_value TO z]')
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

