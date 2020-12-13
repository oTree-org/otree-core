from ibis.errors import TemplateLoadError
import ibis
from pathlib import Path

import ibis
import otree
from ibis import Template
from ibis.errors import TemplateLoadError
from ibis.errors import TemplateRenderingError
from otree import settings
from starlette.responses import HTMLResponse


class FileLoader:
    def __init__(self, *dirs):
        self.dirs = dirs
        self.cache = {}

    def __call__(self, filename):
        if filename in self.cache:
            return self.cache[filename]

        template, path = self.find_template(filename)
        self.cache[filename] = template
        return template

    def find_template(self, filename):
        for dir in self.dirs:
            path = Path(dir, filename)
            if path.exists():
                try:
                    template_string = path.read_text('utf-8')
                except OSError as err:
                    msg = f"FileLoader cannot load the template file '{filename}'."
                    raise TemplateLoadError(msg) from err
                template = Template(template_string, filename)
                return template, path
        msg = f"Loader cannot locate the template file '{filename}'."
        raise TemplateLoadError(msg)


class FileReloader(FileLoader):
    def __call__(self, filename):
        if filename in self.cache:
            cached_mtime, cached_path, cached_template = self.cache[filename]
            if cached_path.exists() and cached_path.stat().st_mtime == cached_mtime:
                return cached_template
        template, path = self.find_template(filename)
        mtime = path.stat().st_mtime
        self.cache[filename] = (mtime, path, template)
        return template


def get_ibis_loader():
    loader_class = FileReloader if settings.DEBUG else FileLoader
    dirs = [Path(otree.__file__).parent.joinpath('templates'), Path('_templates'),] + [
        Path(app_name, 'templates') for app_name in settings.OTREE_APPS
    ]
    return loader_class(*dirs)


ibis_loader = get_ibis_loader()
ibis.loader = ibis_loader


def get_template_name_if_exists(template_names) -> str:
    '''return the path of the first template that exists'''
    for fname in template_names:
        try:
            ibis_loader(fname)
        except TemplateLoadError:
            pass
        else:
            return fname
    raise TemplateLoadError(str(template_names))


def render(template_name, context, **extra_context):
    try:
        return HTMLResponse(
            ibis_loader(template_name).render(
                context, **extra_context, strict_mode=True
            )
        )
    except TemplateRenderingError as exc:
        # for TemplateSyntaxError, i don't see any need to report the original error,
        # as long as the tag is properly written

        # note: the below doesn't work since some exceptions take arguments.

        # location = f' ({exc.token.template_id}, line {exc.token.line_number})'
        # if exc.__cause__:
        #     while exc.__cause__ and isinstance(exc, TemplateError):
        #         exc = exc.__cause__
        #     raise type(exc)(f'"{exc}"' + location).with_traceback(
        #         exc.__traceback__
        #     ) from None
        # raise type(exc)(str(exc) + location)
        raise
