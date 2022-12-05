from pathlib import Path
import os
import otree
from otree import settings
from starlette.responses import HTMLResponse

from .errors import TemplateLoadError


class FileLoader:
    def __init__(self, *dirs):
        self.dirs = dirs
        self.cache = {}

    def load(self, filename: str, template_type=None):
        if filename in self.cache:
            return self.cache[filename]

        template, path = self.load_from_disk(filename, template_type=template_type)
        self.cache[filename] = template
        return template

    def search_template(self, template_id) -> Path:
        for dir in self.dirs:
            path = Path(dir, template_id)
            if path.exists():
                return path
        msg = f"Loader cannot locate the template file '{template_id}'."
        raise TemplateLoadError(msg)

    def load_from_disk(self, template_id, template_type) -> tuple:
        from .template import Template  # todo: resolve circular import

        abspath = self.search_template(template_id)
        try:
            template_string = abspath.read_text('utf-8')
        except OSError as err:
            msg = f"FileLoader cannot load the template file '{abspath}'."
            raise TemplateLoadError(msg) from err
        template = Template(template_string, template_id, template_type=template_type)
        return template, abspath


class FileReloader(FileLoader):
    def load(self, filename: str, template_type=None):
        if filename in self.cache:
            cached_mtime, cached_path, cached_template = self.cache[filename]
            if cached_path.exists() and cached_path.stat().st_mtime == cached_mtime:
                return cached_template
        template, path = self.load_from_disk(filename, template_type=template_type)
        mtime = path.stat().st_mtime
        self.cache[filename] = (mtime, path, template)
        return template


def get_ibis_loader():
    # should it be based on debug? or prodserver vs devserver?
    loader_class = FileReloader if os.getenv('USE_TEMPLATE_RELOADER') else FileLoader

    dirs = [
        Path('.'),  # for noself
        Path('_templates'),
        Path(otree.__file__).parent.joinpath('templates'),
    ] + [Path(app_name, 'templates') for app_name in settings.OTREE_APPS]
    return loader_class(*dirs)


ibis_loader = get_ibis_loader()


def get_template_name_if_exists(template_names) -> str:
    '''return the path of the first template that exists'''
    for fname in template_names:
        try:
            ibis_loader.load(fname)
        except TemplateLoadError:
            pass
        else:
            return fname
    raise TemplateLoadError(str(template_names))


def render(template_name, context, template_type=None, **extra_context):
    return HTMLResponse(
        ibis_loader.load(template_name, template_type=template_type).render(
            context, **extra_context, strict_mode=True
        )
    )
    # i used to modify the traceback to report the original error,
    # but actually i think we shouldn't.
    # The main case I had in mind was if the user calls a method like
    # player.foo(), but it's simpler if they just don't call any complex methods
    # to begin with, and just pass variables to the template.
    # that way we don't go against thre grain
