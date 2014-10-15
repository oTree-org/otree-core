import csv
import datetime
from textwrap import TextWrapper
import inspect
from decimal import Decimal
from django.http import HttpResponse
from django.utils.importlib import import_module
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import user_passes_test
from django.contrib.admin import sites
from django.template.response import TemplateResponse
from inspect_model import InspectModel

import otree.common
import otree.adminlib
from otree.common import app_name_format
import otree.settings
import otree.models
import otree.adminlib
import otree.sessionlib.models
from otree.sessionlib.models import Session, Participant
from otree.adminlib import SessionAdmin, ParticipantAdmin, get_callables, get_all_fields_for_table
from collections import OrderedDict
from otree.db import models
import easymoney

LINE_BREAK = '\r\n'
MODEL_NAMES = ["Participant", "Player", "Group", "Subsession", "Session"]

CONCEPTUAL_OVERVIEW_TEXT = """
oTree data is exported in CSV (comma-separated values) format.

Each field is prefixed by the name of the model it belongs to.

Here is an explanation of these terms:

Session
=======

Refers to an event where a group of people spend time taking part in oTree experiments.

An example of a session would be: "On Tuesday at 3PM, 30 people will come to the lab for 1 hour,
during which time they will play a trust game, followed by 2 ultimatum games, followed by a questionnaire.
Participants get paid EUR 10.00 for showing up, plus bonus amounts for participating.

Subsession
==========

A session can be broken down into "subsessions".
These are interchangeable units or modules that come one after another.
Each subsession has a sequence of one or more pages the player must interact with.
The session in the above example had 4 subsessions:

Trust game
Ultimatum game 1
Ultimatum game 2
Questionnaire

"Player"
=============

Each subsession has data fields for a

and "Participant"
========================================

Each session has a number of players. They are referred to as "participants".

Each subsession has its own "subsession player" (or just "player" for short) objects that are independent of the other subsessions.

If a session has 4 subsessions, for each person there will be 1 sess



"""


def get_data_export_fields(app_label):
    admin_module = import_module('{}._builtin.admin'.format(app_label))
    app_models_module = import_module('{}.models'.format(app_label))
    export_info = {}
    for model_name in MODEL_NAMES:
        if model_name == 'Session':
            Model = otree.sessionlib.models.Session
        elif model_name == 'Participant':
            Model = otree.sessionlib.models.Participant
        else:
            Model = getattr(app_models_module, model_name)

        callables = get_callables(Model, fields_specific_to_this_subclass=None, for_export=True)
        export_member_names = get_all_fields_for_table(Model, callables, first_fields=None, for_export=True)

        # remove anything that isn't a field or method on the model.

        # remove since these are redundant
        export_info[model_name] = {
            'member_names': export_member_names,
            'callables': set(callables)
        }
    return export_info

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
    export_fields = get_data_export_fields(app_label)
    app_models_module = import_module('{}.models'.format(app_label))

    doc_dict = OrderedDict()

    data_types_readable = {
        'PositiveIntegerField': 'positive integer',
        'IntegerField': 'integer',
        'BooleanField': 'boolean',
        'NullBooleanField': 'boolean',
        'CharField': 'text',
        'TextField': 'text',
        'FloatField': 'decimal',
        'DecimalField': 'decimal',
        'MoneyField': 'money',
    }


    for model_name in MODEL_NAMES:
        members = export_fields[model_name]['member_names']
        callables = export_fields[model_name]['callables']
        if model_name == 'Participant':
            Model = otree.sessionlib.models.Participant
        elif model_name == 'Session':
            Model = otree.sessionlib.models.Session
        else:
            Model = getattr(app_models_module, model_name)

        doc_dict[model_name] = OrderedDict()

        for i in range(len(members)):
            member_name = members[i]
            doc_dict[model_name][member_name] = OrderedDict()
            if member_name == 'id':
                doc_dict[model_name][member_name]['type'] = ['positive integer']
                doc_dict[model_name][member_name]['doc'] = ['Unique ID']
            elif member_name in callables:
                member = getattr(Model, member_name)
                doc_dict[model_name][member_name]['doc'] = [inspect.getdoc(member)]
            else:
                member = Model._meta.get_field_by_name(member_name)[0]


                internal_type = member.get_internal_type()
                data_type = data_types_readable.get(internal_type, internal_type)

                doc_dict[model_name][member_name]['type'] = [data_type]

                # flag error if the model doesn't have a doc attribute, which it should
                # unless the field is a 3rd party field
                doc = getattr(member, 'doc', '[error]') or ''
                doc_dict[model_name][member_name]['doc'] = [line.strip() for line in doc.splitlines() if line.strip()]

                choices = getattr(member, 'choices', None)
                if choices:
                    doc_dict[model_name][member_name]['choices'] = choices_readable(choices)

    return doc_dict

def get_docs_as_string(app_label, doc_dict):

    first_line = '{}: Documentation'.format(app_name_format(app_label))
    second_line = '*' * len(first_line)

    lines = [
        first_line,
        second_line,
        '',
        'Accessed: {}'.format(datetime.date.today().isoformat()),
        '',
    ]

    models_module = import_module('{}.models'.format(app_label))
    app_doc = getattr(models_module, 'doc')
    if app_doc:
        lines += [
            app_doc,
            '',
        ]

    for model_name in doc_dict:
        lines.append(model_name)

        for member in doc_dict[model_name]:
            lines.append('\t{}'.format(member))
            for info_type in doc_dict[model_name][member]:
                lines.append('\t\t{}'.format(info_type))
                for info_line in doc_dict[model_name][member][info_type]:
                    lines.append(u'{}{}'.format('\t'*3, info_line))

    output = u'\n'.join(lines)
    return output.replace('\n', LINE_BREAK).replace('\t', '    ')


def data_file_name(app_label):
    return '{} (accessed {}).csv'.format(
        otree.common.app_name_format(app_label),
        datetime.date.today().isoformat(),
    )

def doc_file_name(app_label):
    return '{} - documentation ({}).txt'.format(
        otree.common.app_name_format(app_label),
        datetime.date.today().isoformat()
    )


def get_member_values(object, member_names, callables):
    member_values = []
    for i in range(len(member_names)):
        member_name = member_names[i]
        attr = getattr(object, member_name)
        if member_name in callables:
            member_values.append(attr())
        else:
            member_values.append(attr)
    return member_values


@user_passes_test(lambda u: u.is_staff)
@login_required
def export_list(request):
    # Get unique app_labels
    app_labels = [model._meta.app_label for model, model_admin in sites.site._registry.items()]
    app_labels = list(set(app_labels))
    # Sort the apps alphabetically.
    app_labels.sort()
    # Filter out non subsession apps
    app_labels = [app_label for app_label in app_labels if otree.common.is_subsession_app(app_label)]
    apps = [{"name": app_name_format(app_label), "app_label": app_label} for app_label in app_labels]
    return TemplateResponse(request, "admin/otree_data_export_list.html", {"apps": apps})


@user_passes_test(lambda u: u.is_staff)
@login_required
def export_docs(request, app_label):
    #export = self.model.objects.get(pk=pk)
    #app_label = export.model.app_label
    response = HttpResponse(build_doc_file(app_label))
    response['Content-Disposition'] = 'attachment; filename="{}"'.format(doc_file_name(app_label))
    response['Content-Type'] = 'text/plain'
    return response

@user_passes_test(lambda u: u.is_staff)
@login_required
def export(request, app_label):

    model_names_as_fk = {
        'group': 'Group',
        'subsession': 'Subsession',
        'participant': 'Participant',
        'session': 'Session',
    }

    app_models = import_module('{}.models'.format(app_label))

    Player = app_models.Player

    fk_names = [
        'participant',
        'group',
        'subsession',
        'session',
    ]

    export_data = get_data_export_fields(app_label)

    parent_object_data = {fk_name:{} for fk_name in fk_names}

    column_headers = ['player.{}'.format(member_name) for member_name in export_data['Player']['member_names']]

    for fk_name in fk_names:
        model_name = model_names_as_fk[fk_name]
        member_names = export_data[model_name]['member_names']
        callables = export_data[model_name]['callables']
        column_headers += ['{}.{}'.format(fk_name, member_name) for member_name in member_names]

        # http://stackoverflow.com/questions/2466496/select-distinct-values-from-a-table-field#comment2458913_2468620
        ids = set(Player.objects.order_by().values_list(fk_name, flat=True).distinct())
        if fk_name in {'session', 'participant'}:
            models_module = otree.sessionlib.models
        else:
            models_module = app_models
        objects = getattr(models_module, model_name).objects.filter(pk__in=ids)

        for object in objects:

            parent_object_data[fk_name][object.id] = get_member_values(object, member_names, callables)

    rows = [column_headers[:]]

    # make the CSV output look nicer and easier to work with in other apps
    values_to_replace = {
        None: '',
        True: 1,
        False: 0,
    }
    values_to_replace_keys = values_to_replace.keys()

    for player in Player.objects.all():
        member_names = export_data['Player']['member_names'][:]
        callables = export_data['Player']['callables']
        member_values = get_member_values(player, member_names, callables)
        for fk_name in fk_names:
            parent_object_id = getattr(player, "%s_id" % fk_name)
            if parent_object_id is None:
                model_name = model_names_as_fk[fk_name]
                member_names = export_data[model_name]['member_names']
                member_values += [''] * len(member_names)
            else:
                member_values += parent_object_data[fk_name][parent_object_id]


        for i in range(len(member_values)):
            if member_values[i] in values_to_replace_keys:
                member_values[i] = values_to_replace[member_values[i]]
            elif isinstance(member_values[i], easymoney.Money):
                # remove currency formatting for easier analysis
                member_values[i] = easymoney.to_dec(member_values[i])



        member_values = [unicode(v).encode('UTF-8') for v in member_values]

        # replace line breaks since CSV does not handle line breaks well
        member_values = [v.replace('\n',' ').replace('\r',' ') for v in member_values]

        rows.append(member_values)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="{}"'.format(data_file_name(app_label))
    writer = csv.writer(response)

    writer.writerows(rows)

    return response
