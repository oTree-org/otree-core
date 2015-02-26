#!/usr/bin/env python
# -*- coding: utf-8 -*-


# =============================================================================
# IMPORTS
# =============================================================================

import inspect
import datetime
from collections import OrderedDict

from django.http import HttpResponse
from django.utils.importlib import import_module
from django.contrib.admin import sites
from django.template.response import TemplateResponse

import otree.common_internal
import otree.settings
import otree.models

import otree.models.session
from otree.common_internal import app_name_format

import vanilla


# =============================================================================
# CONSTANTS
# =============================================================================

LINE_BREAK = '\r\n'

MODEL_NAMES = ["Participant", "Player", "Group", "Subsession", "Session"]

CONCEPTUAL_OVERVIEW_TEXT = """
"""


def build_doc_file(app_label):
    doc_dict = get_doc_dict(app_label)
    return get_docs_as_string(app_label, doc_dict)


def choices_readable(choices):
    lines = []
    for value, name in choices:
        # unicode() call is for lazy translation strings
        lines.append(u'{}: {}'.format(value, unicode(name)))

    return lines


def get_doc_dict(app_label):
    export_fields = []  # FIXME: get_data_export_fields(app_label)
    app_models_module = import_module('{}.models'.format(app_label))

    doc_dict = OrderedDict()

    data_types_readable = {
        'PositiveIntegerField': 'positive integer',
        'IntegerField': 'integer',
        'BooleanField': 'boolean',
        'CharField': 'text',
        'TextField': 'text',
        'FloatField': 'decimal',
        'DecimalField': 'decimal',
        'CurrencyField': 'currency',
    }

    for model_name in MODEL_NAMES:
        members = export_fields[model_name]
        if model_name == 'Participant':
            Model = otree.models.session.Participant
        elif model_name == 'Session':
            Model = otree.models.session.Session
        else:
            Model = getattr(app_models_module, model_name)

        doc_dict[model_name] = OrderedDict()

        for i in range(len(members)):
            member_name = members[i]
            member = getattr(Model, member_name, None)
            doc_dict[model_name][member_name] = OrderedDict()
            if member_name == 'id':
                doc_dict[model_name][member_name]['type'] = [
                    'positive integer'
                ]
                doc_dict[model_name][member_name]['doc'] = ['Unique ID']

            elif callable(member):
                doc_dict[model_name][member_name]['doc'] = [
                    inspect.getdoc(member)
                ]
            else:
                member = Model._meta.get_field_by_name(member_name)[0]

                internal_type = member.get_internal_type()
                data_type = data_types_readable.get(
                    internal_type, internal_type
                )

                doc_dict[model_name][member_name]['type'] = [data_type]

                # flag error if the model doesn't have a doc attribute, which
                # it should unless the field is a 3rd party field
                doc = getattr(member, 'doc', '[error]') or ''
                doc_dict[model_name][member_name]['doc'] = [
                    line.strip() for line in doc.splitlines() if line.strip()
                ]

                choices = getattr(member, 'choices', None)
                if choices:
                    doc_dict[model_name][member_name]['choices'] = (
                        choices_readable(choices)
                    )

    return doc_dict


def get_docs_as_string(app_label, doc_dict):

    first_line = '{}: Documentation'.format(app_name_format(app_label))
    second_line = '*' * len(first_line)

    lines = [
        first_line, second_line,
        '', 'Accessed: {}'.format(datetime.date.today().isoformat()), '',
    ]

    models_module = import_module('{}.models'.format(app_label))
    app_doc = getattr(models_module, 'doc')
    if app_doc:
        lines += [app_doc, '']

    for model_name in doc_dict:
        lines.append(model_name)

        for member in doc_dict[model_name]:
            lines.append('\t{}'.format(member))
            for info_type in doc_dict[model_name][member]:
                lines.append('\t\t{}'.format(info_type))
                for info_line in doc_dict[model_name][member][info_type]:
                    lines.append(u'{}{}'.format('\t' * 3, info_line))

    output = u'\n'.join(lines)
    return output.replace('\n', LINE_BREAK).replace('\t', '    ')


def data_file_name(app_label):
    return '{} (accessed {}).csv'.format(
        otree.common_internal.app_name_format(app_label),
        datetime.date.today().isoformat(),
    )


def doc_file_name(app_label):
    return '{} - documentation ({}).txt'.format(
        otree.common_internal.app_name_format(app_label),
        datetime.date.today().isoformat()
    )


class ExportIndex(vanilla.View):

    @classmethod
    def url_pattern(cls):
        return r"^export/$"

    def get(self, request, *args, **kwargs):
        app_labels = [
            model._meta.app_label
            for model, model_admin in sites.site._registry.items()
        ]
        app_labels = list(set(app_labels))
        # Sort the apps alphabetically.
        app_labels.sort()
        # Filter out non subsession apps
        app_labels = [
            app_label
            for app_label in app_labels
            if otree.common_internal.is_subsession_app(app_label)
        ]
        apps = [
            {"name": app_name_format(app_label), "app_label": app_label}
            for app_label in app_labels
        ]
        return TemplateResponse(
            request, "_old_admin/otree_data_export_list.html", {"apps": apps}
        )


class ExportAppDocs(vanilla.View):

    @classmethod
    def url_pattern(cls):
        return r"^export_docs/$"

    def get(self, request, *args, **kwargs):
        app_label = kwargs['app_label']
        # export = self.model.objects.get(pk=pk)
        # app_label = export.model.app_label
        response = HttpResponse(build_doc_file(app_label))
        response['Content-Disposition'] = 'attachment; filename="{}"'.format(
            doc_file_name(app_label)
        )
        response['Content-Type'] = 'text/plain'
        return response
