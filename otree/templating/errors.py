# Base class for all exception types raised by the template engine.
class TemplateError(Exception):
    pass


# This exception type may be raised while attempting to load a template file.
class TemplateLoadError(TemplateError):
    pass


# This exception type is raised if the lexer cannot tokenize a template string.
class TemplateLexingError(TemplateError):
    def __init__(self, msg, template_id, line_number):
        super().__init__(msg)
        self.template_id = template_id
        self.line_number = line_number
        self.msg = msg

    def __str__(self):
        return f'{self.msg} (line {self.line_number})'


class ErrorWithToken(TemplateError):
    def __init__(self, msg, token):
        super().__init__()
        self.msg = msg
        self.token = token

    def __str__(self):
        token = self.token
        return f'{self.msg} (line {token.line_number}, in "{token.keyword}")'


# This exception type may be raised while a template is being compiled.
class TemplateSyntaxError(ErrorWithToken):
    pass


# This exception type may be raised while a template is being rendered.
class TemplateRenderingError(ErrorWithToken):
    pass


# This exception type is raised in strict mode if a variable cannot be resolved.
class UndefinedVariable(ErrorWithToken):
    pass
