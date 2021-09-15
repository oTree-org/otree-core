from . import compiler
from . import context
from . import nodes


class Template:
    def __init__(
        self, template_string, template_id="UNIDENTIFIED", template_type: str = ''
    ):
        is_page_template = template_type in ['Page', 'WaitPage']

        self.root_node = compiler.compile(
            template_string, template_id, is_page_template=is_page_template
        )
        children = self.root_node.children
        # this is so that {% extends 'otree/Page.html' %} can be omitted
        if (
            template_type
            and children
            and not isinstance(children[0], nodes.ExtendsNode)
        ):
            extends = f'otree/{template_type}.html'

            token = compiler.Token(
                'INSTRUCTION', f'extends "{extends}"', template_id, 1
            )
            self.root_node.children.insert(0, nodes.ExtendsNode(token=token))

        self.block_registry = self._register_blocks(self.root_node, {})

    def __str__(self):
        return str(self.root_node)

    def render(self, *pargs, **kwargs):
        data_dict = pargs[0] if pargs else kwargs
        return self.root_node.render(context.Context(data_dict, self))

    def _register_blocks(self, node, registry):
        if isinstance(node, nodes.BlockNode):
            registry.setdefault(node.title, []).append(node)
        for child in node.children:
            self._register_blocks(child, registry)
        return registry
