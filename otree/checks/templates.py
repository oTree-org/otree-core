from django.template.base import TextNode
from django.template.loader_tags import ExtendsNode


class TemplateCheck(object):
    def __init__(self, root):
        self.root = root

    def node_is_empty(self, node):
        if isinstance(node, TextNode):
            return node.s.isspace()
        return False

    def is_extending(self, root):
        return any(
            isinstance(node, ExtendsNode)
            for node in root.nodelist)

    def is_content_node(self, node):
        """
        Returns if the node is an unempty text node.
        """
        if isinstance(node, TextNode):
            return not self.node_is_empty(node)
        return False

    def get_toplevel_content_nodes(self, root):
        nodes = []
        for node in root.nodelist:
            if isinstance(node, ExtendsNode):
                new_child_nodes = self.get_toplevel_content_nodes(node)
                nodes.extend(new_child_nodes)
            if self.is_content_node(node):
                nodes.append(node)
        return nodes

    def get_unreachable_content(self):
        """
        Return all top-level text nodes when the template is extending another
        template. Those text nodes won't be displayed during rendering since
        only content inside of blocks is considered in inheritance.
        """
        if not self.is_extending(self.root):
            return []

        textnodes = self.get_toplevel_content_nodes(self.root)
        content = [node.s for node in textnodes]
        return content


def get_unreachable_content(root):
    check = TemplateCheck(root)
    return check.get_unreachable_content()
