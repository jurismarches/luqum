"""Support for naming expressions

In order to use elastic search named query, we need to be able to assign names to expressions
and retrieve their positions in the query text.

This module adds support for that.

"""
from .utils import LuceneTreeVisitorV2


#: Names are added to tree items via an attribute named `_luqum_name`
NAME_ATTR = "_luqum_name"


def set_name(node, value):
    setattr(node, NAME_ATTR, value)


def get_name(node):
    return getattr(node, NAME_ATTR, None)


class TreeAutoNamer(LuceneTreeVisitorV2):
    # helper for :py:func:`tree_name_index`

    def visit_base_operation(self, node, parents=None, context=None):
        # operations are the splitting point, we name them and make children subnames
        names = context["names"]
        set_name(node, ("_".join(names)))
        for i, c in enumerate(node.children):
            self.visit(c, context={"names": names + [str(i)]})

    def visit_term(self, node, parents=None, context=None):
        names = context["names"]
        set_name(node, ("_".join(names)))

    def visit_range(self, node, parents=None, context=None):
        names = context["names"]
        set_name(node, ("_".join(names)))
        # no need to visit children

    def generic_visit(self, node, parents=None, context=None):
        # just propagate to children
        for c in node.children:
            self.visit(c, context=context)

    def visit(self, node, parents=None, context=None):
        # just initialise context
        if context is None:
            context = {"names": ["0"]}
        return super().visit(node, parents, context=context)


def auto_name(tree):
    """Automatically add names to nodes of a parse tree.

    We add them to terminal nodes : range, phrases and words, as this is where it is useful,
    but also on operations, to easily grab the group.
    """
    TreeAutoNamer().visit(tree)


class NameIndexer(LuceneTreeVisitorV2):
    # helper for :py:func:`tree_name_index`

    def generic_visit(self, node, parents=None, context=None):
        # visit children
        sub_names = []
        for child in node.children:
            sub_names.extend(self.visit(child, parents=True))
        name = get_name(node)
        root_node = not parents
        if name is not None or root_node:
            str_repr = str(node)
            # search for subnodes position
            subnodes_pos = []
            idx = 0
            for (subname, sub_repr, sub_subnodes_pos) in sub_names:
                pos = str_repr.find(sub_repr, idx)
                if pos >= 0:  # pragma: no branch
                    l = len(sub_repr)
                    subnodes_pos.append((subname, pos, l, sub_subnodes_pos))
                    idx = pos + l
            sub_names = [(name, str_repr, subnodes_pos)]
        return sub_names

    def __call__(self, node):
        subnames = self.visit(node, parents=False)
        # by construction, root node, only return one entry
        name, str_repr, subnodes_pos = subnames[0]
        if name is not None:
            # resolve last level
            subnodes_pos = [(name, 0, len(str_repr), subnodes_pos)]
        return subnodes_pos


def _flatten_name_index(subnodes_pos, start_pos=0):
    for name, pos, length, children in subnodes_pos:
        yield name, start_pos + pos, length
        yield from _flatten_name_index(children, start_pos + pos)


def name_index(tree):
    """Given a tree with names, give the index of each group in the string representation.
    also gives the node type.

    .. warning:: this is not an efficient implementation,
        It will call str representation several times on each item, and seek for substrings.

        see :py:class:`TreeNameIndexer`


    :param tree: a luqum parse tree
    :return dict: mapping each name to a `(start position, length)` tuple
    """
    subnodes_pos = NameIndexer()(tree)
    # flatten the hierarchy
    result = {name: (pos, length) for name, pos, length in _flatten_name_index(subnodes_pos)}
    return result


def extract(expr, name, name_index):
    """extract named part of expression, using name_index

    :param str expr: the lucene expression
    :param str name: name of the part to extract
    :param dict name_index: the dict obtained from :py:func:`name_index`
    """
    return expr[name_index[name][0]: name_index[name][0] + name_index[name][1]]
