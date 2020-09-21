"""It can be teadious to add spaces in a tree you generate programatically.

This module provide a utility to transform a tree so that it contains necessary head/tail
for expression to be printable.
"""

from . import visitor


class AutoHeadTail(visitor.TreeTransformer):
    """This class implements a transformer so that hand built tree,
    can have reasonable values for `head` and `tail` on their items,
    in order for the expression to be printable.
    """

    SPACER = " "

    def add_head(self, node):
        if not node.head:
            node.head = self.SPACER

    def add_tail(self, node):
        if not node.tail:
            node.tail = self.SPACER

    def visit_base_operation(self, node, context):
        new_node = node.clone_item()
        children = list(self.clone_children(node, new_node, context))
        # add tail to first node
        self.add_tail(children[0])
        # add head and tail to inner nodes
        for child in children[1:-1]:
            self.add_head(child)
            self.add_tail(child)
        # add head to last
        self.add_head(children[-1])
        new_node.children = children
        yield new_node

    def visit_unknown_operation(self, node, context):
        new_node = node.clone_item()
        children = list(self.clone_children(node, new_node, context))
        # add tail to each node, but last
        for child in children[:-1]:
            self.add_tail(child)
        new_node.children = children
        yield new_node

    def visit_not(self, node, context):
        new_node = node.clone_item()
        children = list(self.clone_children(node, new_node, context))
        # add head to children, to have space between NOT and sub expression
        self.add_head(children[0])
        new_node.children = children
        yield new_node

    def visit_range(self, node, context):
        new_node = node.clone_item()
        children = list(self.clone_children(node, new_node, context))
        # add tail to lower_bound, and head to upper bound
        self.add_tail(children[0])
        self.add_head(children[-1])
        new_node.children = children
        yield new_node

    def __call__(self, tree):
        new_tree = self.visit(tree)
        return new_tree


auto_head_tail = AutoHeadTail()
"""method to auto add head and tail to items of a lucene tree so that it is printable
"""
