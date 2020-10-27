# -*- coding: utf-8 -*-
"""Base classes to implement a visitor pattern.
"""


def camel_to_lower(name):
    return "".join(
        "_" + w.lower() if w.isupper() else w.lower()
        for w in name).lstrip("_")


class TreeVisitor:
    """
    Tree Visitor base class.

    This class is meant to be subclassed, with the subclass implementing
    visitor methods for each Node type it is interested in.

    By default, those visitor method should be named ``'visit_'`` + class
    name of the node, converted to lower_case (ie: visit_search_node for a
    SearchNode class)[#tweakvisit]_.

    It's up to the visit method of each node to recursively call children (or not)
    It may be done simply by calling the generic_visit method.

    By default the `generic_visit`, simply trigger visit of subnodes, yielding no information.

    If the goal is to modify the initial tree, to get a new modified copy
    use :py:class:`TreeTranformer` instead.

    .. [#tweakvisit]: You can tweak this behaviour
       by overriding the `visitor_method_prefix` & `generic_visitor_method_name` class attributes.

    :param bool track_parents: if True the context will contain parents of current node as a list.
        It's up to you to maintain this list in your own methods.
    """
    visitor_method_prefix = 'visit_'
    generic_visitor_method_name = 'generic_visit'

    def __init__(self, track_parents=False):
        self.track_parents = track_parents

    _get_method_cache = None

    def _get_method(self, node):
        if self._get_method_cache is None:
            self._get_method_cache = {}
        try:
            meth = self._get_method_cache[type(node)]
        except KeyError:
            for cls in node.__class__.mro():
                try:
                    method_name = "{}{}".format(
                        self.visitor_method_prefix,
                        camel_to_lower(cls.__name__)
                    )
                    meth = getattr(self, method_name)
                    break
                except AttributeError:
                    continue
            else:
                meth = getattr(self, self.generic_visitor_method_name)
            self._get_method_cache[type(node)] = meth
        return meth

    def visit(self, tree, context=None):
        """Traversal of tree

        :param luqum.tree.Item tree: a tree representing a lucene expression
        :param dict context: a dict with initial values for context

        .. note:: the values in context, are not guaranteed to move up the hierachy,
           because we do copy of context for children to have specific values.

           A trick you can use if you need values to move up the hierachy
           is to set a `"global"` key containing a dict, where you can store values.
        """
        if context is None:
            context = {}
        return list(self.visit_iter(tree, context=context))

    def visit_iter(self, node, context):
        """
        Basic, recursive traversal of the tree.

        :param list parents: the list of parents
        :param dict context: a dict of contextual variable for free use
            to track states while traversing the tree (eg. the current field name)
        """
        method = self._get_method(node)
        yield from method(node, context)

    def child_context(self, node, child, context, **kwargs):
        """Generate a context for children.

        The context children is distinct from its parent context,
        so that visit in a branch does not affect others.

        .. note:: If you need global parameters,
            a trick is to put them in dict in a "global" entry
            as we do a swallow copy of context, and not a deep one.

        :param luqum.tree.Item node: parent node
        :param luqum.tree.Item child: child node
        :param dict context: parent context
        :return dict: child context
        """
        child_context = dict(context)
        if self.track_parents:
            child_context["parents"] = context.get("parents", ()) + (node,)
        return child_context

    def generic_visit(self, node, context):
        """
        Default visitor function, called if nothing matches the current node.

        It simply visit children.

        :param luqum.tree.Item node: current node
        :param dict context: context (aka local parameters received from parents)
        """
        for child in node.children:
            child_context = self.child_context(node, child, context)
            yield from self.visit_iter(child, context=child_context)


class TreeTransformer(TreeVisitor):
    """A version of TreeVisitor that is aimed at obtaining a transformed copy of tree.

    .. note:: It is far better to build a transformed copy,
        than to modify in place the original tree, as it is less error prone.

    :param bool track_new_parents: do we want to track new parents in the context ?
    """

    def __init__(self, track_new_parents=False, **kwargs):
        self.track_new_parents = track_new_parents
        super().__init__(**kwargs)

    def _clone_item(self, node):
        """simply call node.clone_item

        Surcharge this method to add specific tweaks if needed (like copying special attributes)
        """
        return node.clone_item()

    def visit(self, tree, context=None):
        """Visit the tree, by default building a copy and returning it.

        :param luqum.tree.Item tree: luqum expression tree
        :param context: optional initial context
        """
        if context is None:
            context = {}
        try:
            value, = self.visit_iter(tree, context=context)
            return value
        except ValueError as e:
            if str(e).startswith(("too many values to unpack", "not enough values to unpack")):
                exc = ValueError(
                    "The visit of the tree should have produced exactly one element "
                    "(the transformed tree)"
                )
                raise exc from e
            else:
                raise

    def child_context(self, node, child, context, **kwargs):
        child_context = super().child_context(node, child, context, **kwargs)
        if self.track_new_parents:
            child_context["new_parents"] = context.get("new_parents", ()) + (kwargs["new_node"],)
        return child_context

    def generic_visit(self, node, context):
        """
        Default visitor function, called if nothing matches the current node.

        It simply clone node and children
        """
        new_node = self._clone_item(node)
        new_node.children = list(self.clone_children(node, new_node, context))
        yield new_node

    def clone_children(self, node, new_node, context):
        """Helper to clone children.

        .. note:: a children may generate more than one children or none, for flexibility
           but it's up to the transformer to ensure everything is ok
        """
        for child in node.children:
            child_context = self.child_context(node, child, context, new_node=new_node)
            new_children = self.visit_iter(child, context=child_context)
            for new_child in new_children:
                yield new_child


class PathTrackingMixin:
    """It can be useful to compute path of an element (as tuple of index in parent children)

    This mixin provides base components
    """

    def child_context(self, node, child, context, **kwargs):
        """Thanks to "path" and "position" in kwargs, we add the path of children
        """
        child_context = super().child_context(node, child, context, **kwargs)
        child_context["path"] = context["path"] + (kwargs["position"],)
        return child_context

    def visit(self, node, context=None):
        """visit the tree while tracking their path
        """
        if context is None:
            context = {}
        context["path"] = ()
        return super().visit(node, context=context)


class PathTrackingVisitor(PathTrackingMixin, TreeVisitor):
    """Path tracking version of TreeVisitor
    """

    def generic_visit(self, node, context):
        for i, child in enumerate(node.children):
            child_context = self.child_context(node, child, context, position=i)
            yield from self.visit_iter(child, context=child_context)


class PathTrackingTransformer(PathTrackingMixin, TreeTransformer):
    """Path tracking version of TreeTransformer
    """

    def clone_children(self, node, new_node, context):
        for i, child in enumerate(node.children):
            child_context = self.child_context(node, child, context, new_node=new_node, position=i)
            new_children = self.visit_iter(child, context=child_context)
            for new_child in new_children:
                yield new_child
