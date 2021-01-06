"""Support for naming expressions

In order to use elastic search named query, we need to be able to assign names to expressions
and retrieve their positions in the query text.

This module adds support for that.
"""
from . import tree
from .visitor import PathTrackingVisitor, PathTrackingTransformer


#: Names are added to tree items via an attribute named `_luqum_name`
NAME_ATTR = "_luqum_name"


def set_name(node, value):
    setattr(node, NAME_ATTR, value)


def get_name(node):
    return getattr(node, NAME_ATTR, None)


class TreeAutoNamer(PathTrackingVisitor):
    """Helper for :py:func:`auto_name`
    """

    LETTERS = "abcdefghilklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    _pos_letter = {l: i for i, l in enumerate(LETTERS)}

    def next_name(self, name):
        """Given name, return next name

        ::
           >>> tan = TreeAutoNamer()
           >>> tan.next_name(None)
           'a'
           >>> tan.next_name('aZ')
           'aZa'
           >>> tan.next_name('azb')
           'azc'
        """
        if name is None:
            # bootstrap
            return self.LETTERS[0]
        else:
            actual_pos = self._pos_letter[name[-1]]
            try:
                # we want to increment last letter
                return name[:-1] + self.LETTERS[actual_pos + 1]
            except IndexError:
                # we exhausts letters, add a new one instead
                return name + self.LETTERS[0]

    def visit_base_operation(self, node, context):
        """name is to be set on children of operations
        """
        # put a _name on each children
        name = context["global"]["name"]
        for i, child in enumerate(node.children):
            name = self.next_name(name)
            set_name(child, name)
            # remember name to path
            context["global"]["name_to_path"][name] = context["path"] + (i,)
        # put name back in global context
        context["global"]["name"] = name
        yield from self.generic_visit(node, context)

    def visit(self, node):
        """visit the tree and add names to nodes while tracking their path
        """
        # trick: we use a "global" dict inside context dict so that when we copy context,
        # we still track the same objects
        context = {"global": {"name": None, "name_to_path": {}}}
        super().visit(node, context)
        name_to_path = context["global"]["name_to_path"]
        # handle special case, if we have no name so far, put one on the root
        if not name_to_path:
            node_name = self.next_name(context["global"]["name"])
            set_name(node, node_name)
            name_to_path[node_name] = ()
        return name_to_path


def auto_name(tree, targets=None, all_names=False):
    """Automatically add names to nodes of a parse tree, in order to be able to track matching.

    We add them to top nodes under operations as this is where it is useful for ES named queries

    :return dict: association of name with the path (as a tuple) to a the corresponding children
    """
    return TreeAutoNamer().visit(tree)


def matching_from_names(names, name_to_path):
    """Utility to convert a list of name and the result of auto_name
    to the matching parameter for :py:class:`MatchingPropagator`

    :param list names: list of names
    :param dict name_to_path: association of names with path to children
    :return tuple: (set of matching paths, set of other known paths)
    """
    matching = {name_to_path[name] for name in names}
    return (matching, set(name_to_path.values()) - matching)


def element_from_path(tree, path):
    """Given a tree, retrieve element corresponding to path

    :param luqum.tree.Item tree: luqum expression tree
    :param tuple path: tuple representing top down access to a child
    :return  luqum.tree.Item: target item
    """
    # python likes iterations over recursivity
    node = tree
    path = list(path)
    while path:
        node = node.children[path.pop(0)]
    return node


def element_from_name(tree, name, name_to_path):
    return element_from_path(tree, name_to_path[name])


class MatchingPropagator:
    """Class propagating matching to upper elements based on known base element matching

    :param luqum.tree.Item default_operation: tells how to treat UnknownOperation.
        Choose between :py:class:`luqum.tree.OrOperation` and :py:class:`luqum.tree.AndOperation`
    """

    OR_NODES = (tree.OrOperation,)
    """A tuple of nodes types considered as OR operations
    """
    NEGATION_NODES = (tree.Not, tree.Prohibit)
    """A tuple of nodes types considered as NOT operations
    """
    NO_CHILDREN_PROPAGATE = (tree.Range, tree.BaseApprox)
    """A tuple of nodes for which propagation is of no use
    """

    def __init__(self, default_operation=tree.OrOperation):
        if default_operation is tree.OrOperation:
            self.OR_NODES = self.OR_NODES + (tree.UnknownOperation,)

    def _status_from_parent(self, path, matching, other):
        """Get status from nearest parent in hierarchie which had a name
        """
        if path in matching:
            return True
        elif path in other:
            return False
        elif not path:
            return False
        else:
            return self._status_from_parent(path[:-1], matching, other)

    def _propagate(self, node, matching, other, path):
        """recursively propagate matching

        return tuple: (
            node is matching,
            set of pathes of matching sub nodes,
            set of pathes of non matching sub nodes)
        """
        paths_ok = set()  # path of nodes that are matching
        paths_ko = set()  # path of nodes that are not matching
        children_status = []  # bool for each children, indicating if it matches or not
        # recurse children
        if node.children and not isinstance(node, self.NO_CHILDREN_PROPAGATE):
            for i, child in enumerate(node.children):
                child_ok, sub_ok, sub_ko = self._propagate(
                    child, matching, other, path + (i,),
                )
                paths_ok.update(sub_ok)
                paths_ko.update(sub_ko)
                children_status.append(child_ok)
        # resolve node status
        if path in matching:
            node_ok = True
        elif children_status:  # compute from children
            # compute parent success from children
            operator = any if isinstance(node, self.OR_NODES) else all
            node_ok = operator(children_status)
        else:
            node_ok = self._status_from_parent(path, matching, other)
        if isinstance(node, self.NEGATION_NODES):
            # negate result
            node_ok = not node_ok
        # add node to the right set
        target_set = paths_ok if node_ok else paths_ko
        target_set.add(path)
        # return result
        return node_ok, paths_ok, paths_ko

    def __call__(self, tree, matching, other=frozenset()):
        """
        Given a list of paths that are known to match,
        return all pathes in the tree that are matches.

        .. note:: we do not descend into nodes that are positive.
           Normally matching just provides nodes at the right levels
           for propagation to be effective.
           Descending would mean risking to give non consistent information.

        :param list matching: list of path of matching nodes (each path is a tuple)
        :param list other: list of other path that had a name, but were not reported as matching

        :return tuple: (
            set of matching path after propagation,
            set of non matching pathes after propagation)
        """
        tree_ok, paths_ok, paths_ko = self._propagate(tree, matching, other, ())
        return paths_ok, paths_ko


class ExpressionMarker(PathTrackingTransformer):
    """A visitor to mark a tree based on elements belonging to a path or not

    One intended usage is to add marker around nodes matching a request,
    by altering tail and head of elements
    """

    def mark_node(self, node, path, *info):
        """implement this in your own code, maybe altering the head / tail arguments
        """
        return node

    def generic_visit(self, node, context):
        # we simply generate new_node and mark it
        new_node, = super().generic_visit(node, context)
        yield self.mark_node(new_node, context["path"], *context["info"])

    def __call__(self, tree, *info):
        return self.visit(tree, context={"info": info})


class HTMLMarker(ExpressionMarker):
    """from paths that are ok or ko, add html elements with right class around elements

    :param str ok_class: class for elements in paths_ok
    :param str ko_class: class for elements in paths_ko
    :param str element: html element used to surround sub expressions
    """

    def __init__(self, ok_class="ok", ko_class="ko", element="span"):
        super().__init__()
        self.ok_class = ok_class
        self.ko_class = ko_class
        self.element = element

    def css_class(self, path, paths_ok, paths_ko):
        return self.ok_class if path in paths_ok else self.ko_class if path in paths_ko else None

    def mark_node(self, node, path, paths_ok, paths_ko, parcimonious):
        node_class = self.css_class(path, paths_ok, paths_ko)
        add_class = node_class is not None
        if add_class and parcimonious:
            # find nearest parent with a class
            parent_class = None
            parent_path = path
            while parent_class is None and parent_path:
                parent_path = parent_path[:-1]
                parent_class = self.css_class(parent_path, paths_ok, paths_ko)
            # only add class if different from parent
            add_class = node_class != parent_class
        if add_class:
            node.head = f'<{self.element} class="{node_class}">{node.head}'
            node.tail = f'{node.tail}</{self.element}>'
        return node

    def __call__(self, tree, paths_ok, paths_ko, parcimonious=True):
        """representation of tree, adding html elements with right class around subexpressions
        according to their presence in paths_ok or paths_ko

        :param tree: a luqum tree
        :param paths_ok: set of path to nodes (express as tuple of int) that should get ok_class
        :param paths_ko: set of path to nodes that should get ko_class
        :param parcimonious: only add class when parent node does not have same class

        :return str: expression with html elements surrounding part of expression
          with right class attribute according to paths_ok and paths_ko
        """
        new_tree = super().__call__(tree, paths_ok, paths_ko, parcimonious)
        return new_tree.__str__(head_tail=True)
