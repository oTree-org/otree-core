from . import nodes
from . import errors


# Token delimiters.
COMMENT_START = '{#'
COMMENT_END = '#}'
INSTRUCTION_START_OLD = '{%'
INSTRUCTION_END_OLD = '%}'
INSTRUCTION_START = '{{'
INSTRUCTION_END = '}}'


# Returns the root node of the compiled node tree.
def compile(template_string, template_id):
    return Parser(template_string, template_id).parse()


# Tokens come in four different types: TEXT, PRINT, EPRINT, and INSTRUCTION.
class Token:
    def __init__(self, token_type, token_text, template_id, line_number):
        words = token_text.split()
        self.keyword = words[0] if words else ''
        self.type = token_type
        self.text = token_text
        self.template_id = template_id
        self.line_number = line_number

    def __str__(self):
        return (
            f"({self.type}, {repr(self.text)}, {self.template_id}, {self.line_number})"
        )


# The Lexer takes a template string as input and chops it into a list of Tokens.
class Lexer:
    def __init__(self, template_string, template_id):
        self.template_string = template_string
        self.template_id = template_id
        self.tokens = []
        self.index = 0
        self.line_number = 1

    def tokenize(self):
        while self.index < len(self.template_string):
            if self.match(COMMENT_START):
                self.read_comment_tag()
            elif self.match(INSTRUCTION_START) or self.match(INSTRUCTION_START_OLD):
                self.read_instruction_tag()
            else:
                self.read_text()
        return self.tokens

    def match(self, target):
        if self.template_string.startswith(target, self.index):
            return True
        return False

    def advance(self):
        if self.template_string[self.index] == '\n':
            self.line_number += 1
        self.index += 1

    def read_comment_tag(self):
        self.index += len(COMMENT_START)
        start_line_number = self.line_number
        while self.index < len(self.template_string):
            if self.match(COMMENT_END):
                self.index += len(COMMENT_END)
                return
            self.advance()
        msg = f"Unclosed comment tag"
        raise errors.TemplateLexingError(msg, self.template_id, start_line_number)

    def read_instruction_tag(self):
        self.index += len(INSTRUCTION_START)
        start_index = self.index
        start_line_number = self.line_number
        while self.index < len(self.template_string):
            if self.match(INSTRUCTION_END) or self.match(INSTRUCTION_END_OLD):
                text = self.template_string[start_index : self.index].strip()
                self.tokens.append(
                    Token("INSTRUCTION", text, self.template_id, start_line_number)
                )
                self.index += len(INSTRUCTION_END)
                return
            self.advance()
        msg = f"Unclosed instruction tag"
        raise errors.TemplateLexingError(msg, self.template_id, start_line_number)

    def read_text(self):
        start_index = self.index
        start_line_number = self.line_number
        while self.index < len(self.template_string):
            if self.match(COMMENT_START):
                break
            elif self.match(INSTRUCTION_START) or self.match(INSTRUCTION_START_OLD):
                break
            self.advance()
        text = self.template_string[start_index : self.index]
        self.tokens.append(Token("TEXT", text, self.template_id, start_line_number))


# The Parser takes a template string as input, lexes it into a token stream, then compiles the
# token stream into a tree of nodes.
class Parser:
    def __init__(self, template_string, template_id):
        self.template_string = template_string
        self.template_id = template_id

    def parse(self):
        stack = [nodes.Node()]
        expecting = []

        for token in Lexer(self.template_string, self.template_id).tokenize():
            if token.type == "TEXT":
                stack[-1].children.append(nodes.TextNode(token))
            elif token.keyword in nodes.instruction_keywords:
                node_class, endword = nodes.instruction_keywords[token.keyword]
                node = node_class(token)
                stack[-1].children.append(node)
                if endword:
                    stack.append(node)
                    expecting.append(endword)
            elif token.keyword in nodes.instruction_endwords:
                if len(expecting) == 0:
                    msg = f"Unexpected tag"
                    raise errors.TemplateSyntaxError(msg, token)
                elif expecting[-1] != token.keyword:
                    msg = (
                        f"Unexpected '{token.keyword}' tag. "
                        f"Was expecting the following closing tag: '{expecting[-1]}'."
                    )
                    raise errors.TemplateSyntaxError(msg, token)
                else:
                    stack[-1].exit_scope()
                    stack.pop()
                    expecting.pop()
            elif token.keyword == '':
                msg = f"Empty instruction tag"
                raise errors.TemplateSyntaxError(msg, token)
            else:
                stack[-1].children.append(nodes.PrintNode(token))

        if expecting:
            token = stack[-1].token
            msg = (
                f"Unexpected end of template. "
                f"Was expecting a closing tag '{expecting[-1]}' to close the "
                f"'{token.keyword}' tag opened in line {token.line_number}."
            )
            raise errors.TemplateSyntaxError(msg, token)

        return stack.pop()
