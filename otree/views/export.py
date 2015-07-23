#!/usr/bin/env python
# -*- coding: utf-8 -*-


# =============================================================================
# IMPORTS
# =============================================================================

import inspect
import datetime
import csv
from collections import OrderedDict
from importlib import import_module

from django.http import HttpResponse
from django.conf import settings

import vanilla

import otree.common_internal
import otree.models
import otree.models.session
from otree.common_internal import app_name_format
from otree.views.admin import get_display_table_rows, get_all_fields
from otree.models_concrete import PageCompletion


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
        if model_name == 'Participant':
            Model = otree.models.session.Participant
        elif model_name == 'Session':
            Model = otree.models.session.Session
        else:
            Model = getattr(app_models_module, model_name)

        members = get_all_fields(Model, for_export=True)
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


class ExportIndex(vanilla.TemplateView):

    template_name = 'otree/export/index.html'

    @classmethod
    def url_pattern(cls):
        return r"^export/$"

    @classmethod
    def url_name(cls):
        return 'export'

    def get_context_data(self, **kwargs):
        context = super(ExportIndex, self).get_context_data(**kwargs)
        app_labels = settings.INSTALLED_OTREE_APPS
        app_labels_with_data = []
        for app_label in app_labels:
            model_module = otree.common_internal.get_models_module(app_label)
            if model_module.Player.objects.exists():
                app_labels_with_data.append(app_label)
        apps = [
            {"name": app_name_format(app_label), "label": app_label}
            for app_label in app_labels_with_data
        ]
        context.update({'apps': apps})
        return context


class ExportAppDocs(vanilla.View):

    @classmethod
    def url_pattern(cls):
        return r"^ExportAppDocs/(?P<app_label>\w+)/$"

    @classmethod
    def url_name(cls):
        return 'export_app_docs'

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


class ExportCsv(vanilla.View):

    @classmethod
    def url_pattern(cls):
        return r"^ExportCsv/(?P<app_label>\w+)/$"

    @classmethod
    def url_name(cls):
        return 'export_csv'

    def get(self, request, *args, **kwargs):
        app_label = kwargs['app_label']
        colnames, rows = get_display_table_rows(
            app_label, for_export=True, subsession_pk=None
        )
        colnames = ['{}.{}'.format(k, v) for k, v in colnames]
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="{}"'.format(
            data_file_name(app_label)
        )
        writer = csv.writer(response)
        writer.writerows([colnames])
        writer.writerows(rows)
        return response


class ExportTimeSpent(vanilla.View):

    @classmethod
    def url_pattern(cls):
        return r"^ExportTimeSpent/$"

    @classmethod
    def url_name(cls):
        return 'export_time_spent'

    def get(self, request, *args, **kwargs):
        columns = get_all_fields(PageCompletion)
        rows = PageCompletion.objects.order_by(
            'session_pk', 'participant_pk', 'page_index'
        ).values_list(*columns)
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="{}"'.format(
            'TimeSpent (accessed {}).csv'.format(
                datetime.date.today().isoformat()
            )
        )
        writer = csv.writer(response)
        writer.writerows([columns])
        writer.writerows(rows)
        return response
