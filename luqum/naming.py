"""Support for naming expressions

In order to use elastic search named query, we need to be able to assign names to expressions
and retrieve their positions in the query text.

This module adds support for that.
"""
from . import tree
from .visitor import TreeVisitor


#: Names are added to tree items via an attribute named `_luqum_name`
NAME_ATTR = "_luqum_name"


def set_name(node, value):
    setattr(node, NAME_ATTR, value)


def get_name(node):
    return getattr(node, NAME_ATTR, None)


class TreeAutoNamer(TreeVisitor):
    # helper for :py:func:`tree_name_index`

    DEFAULT_TARGETS = (tree.Range, tree.Term, tree.Fuzzy, tree.BaseApprox)
    """by default targets are the one translated to a leaf term in elasticsearch

    :param tuple targets: class of elements that should receive a name
    :param bool all_names: shall we name children of named elements ?
    """

    LETTERS = "abcdefghilklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    _letter_pos = {i: l for i, l in enumerate(LETTERS)}
    _pos_letter = {l: i for i, l in enumerate(LETTERS)}

    def __init__(self, targets=None, all_names=False):
        self.targets = targets if targets is not None else self.DEFAULT_TARGETS
        self.all_names = all_names
        super().__init__(track_parents=False)

    def generic_visit(self, node, context):
        visit_children = True
        if isinstance(node, self.targets):
            # add name
            self.context["name"] = name = self.next_name(context["name"])
            set_name(node, name)
            # track name / path correspondance
            context["name_to_path"][name] = tuple(context["path"])
            visit_children = self.all_names
        if visit_children:
            # continue with path trackings
            for i, child in enumerate(node.children):
                child_context = dict(context, path=context["path"] + [i])
                yield from self.visit_iter(child, context=child_context)
        else:
            yield node

    def visit(self, node):
        """visit the tree and add names to nodes while tracking their path
        """
        context = {"path": [], "name": None, "name_to_path": {}}
        list(self.visit_iter(node, context=context))
        return context["name_to_path"]


def auto_name(tree, targets=None, all_names=False):
    """Automatically add names to nodes of a parse tree.

    We add them to terminal nodes : range, phrases and words, as this is where it is useful.

    :return: a dict giving the path to a the children having this name
    """
    return TreeAutoNamer().visit(tree, targets, all_names)


def name_index(tree, name_to_path):
    """Given a tree with names, give the index of each group in the string representation.
    also gives the node type.

    .. warning:: this is not an efficient implementation,
        It will call str representation several times on each item, and seek for substrings.

        see :py:class:`TreeNameIndexer`


    :param tree: a luqum parse tree
    :return dict: mapping each name to a `(start position, length)` tuple
    """


def extract(expr, name, name_index):
    """extract named part of expression, using name_index

    :param str expr: the lucene expression
    :param str name: name of the part to extract
    :param dict name_index: the dict obtained from :py:func:`name_index`
    """
    return expr[name_index[name][0]: name_index[name][0] + name_index[name][1]]
