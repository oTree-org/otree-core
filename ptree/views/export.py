import csv
import datetime
from textwrap import TextWrapper
import inspect

from django.http import HttpResponse
from django.utils.importlib import import_module
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import user_passes_test
from django.contrib.admin import sites
from django.shortcuts import render_to_response
from inspect_model import InspectModel

import ptree.common
import ptree.adminlib
from ptree.common import app_name_format
import ptree.settings
import ptree.models
import ptree.adminlib
import ptree.sessionlib.models
from ptree.adminlib import SessionAdmin, SessionParticipantAdmin


LINE_BREAK = '\r\n'
MODEL_NAMES = ["Participant", "Match", "Treatment", "Subsession", "SessionParticipant", "Session"]


def get_data_export_fields(app_label):
    admin_module = import_module('{}.admin'.format(app_label))
    app_models_module = import_module('{}.models'.format(app_label))
    export_info = {}
    for model_name in MODEL_NAMES:
        if model_name == 'Session':
            Model = ptree.sessionlib.models.Session
            export_member_names = SessionAdmin.list_display
        elif model_name == 'SessionParticipant':
            Model = ptree.sessionlib.models.SessionParticipant
            export_member_names = SessionParticipantAdmin.list_display
        else:
            export_member_names = getattr(admin_module, '{}Admin'.format(model_name)).list_display
            Model = getattr(app_models_module, model_name)

        # remove anything that isn't a field or method on the model.

        im = InspectModel(Model)
        exportable_members = set(im.fields + im.methods)
        methods = set(im.methods)

        export_member_names = [m for m in export_member_names if (m in exportable_members
                                                                  and not m in {'match', 'treatment', 'subsession', 'session'})]
        callable_flags = [member_name in methods for member_name in export_member_names]

        # remove since these are redundant
        export_info[model_name] = {
            'member_names': export_member_names,
            'callable_flags': callable_flags
        }
    return export_info

def build_doc_file(app_label):
    export_fields = get_data_export_fields(app_label)
    app_models_module = import_module('{}.models'.format(app_label))

    first_line = '{}: Documentation'.format(app_name_format(app_label))

    docs = ['{}\n{}\n\n'.format(first_line,
                                '*'*len(first_line))]

    doc_string_wrapper = TextWrapper(
        width=100,
        initial_indent='\t'*2,
        subsequent_indent='\t'*2
    )

    for model_name in MODEL_NAMES:
        members = export_fields[model_name]['member_names']
        callable_flags = export_fields[model_name]['callable_flags']
        if model_name == 'SessionParticipant':
            Model = ptree.sessionlib.models.SessionParticipant
        elif model_name == 'Session':
            Model = ptree.sessionlib.models.Session
        else:
            Model = getattr(app_models_module, model_name)

        docs.append('\n' + model_name)

        for i in range(len(members)):
            member_name = members[i]
            is_callable = callable_flags[i]
            if is_callable:
                member = getattr(Model, member_name)
                doc = inspect.getdoc(member)
            else:
                try:
                    member = Model._meta.get_field_by_name(member_name)[0]
                    doc = member.doc
                except AttributeError:
                    # maybe the field isn't from ptree.db
                    doc = '[error]'
            docs.append('\n\t%s' % member_name)
            if doc:
                docs.append('\n'.join(doc_string_wrapper.wrap(doc)))

    output = '\n'.join(docs)
    return output.replace('\n', LINE_BREAK).replace('\t', '    ')

def doc_file_name(app_label):
    return '{} - documentation.txt'.format(app_name_format(app_label))

nyi = """
class PTreeExportAdmin(ExportAdmin):

    # In Django 1.7, I can set list_display_links to None and then put 'name' first
    list_display = ['get_export_link', 'docs_link', 'name']
    ordering = ['slug']
    list_filter = []

    def get_urls(self):
        urls = super(PTreeExportAdmin, self).get_urls()
        my_urls = patterns('',
            (r'^(?P<pk>\d+)/docs/$', self.admin_site.admin_view(self.docs)),
        )
        return my_urls + urls

    def docs(self, request, pk):
        export = self.model.objects.get(pk=pk)
        app_label = export.model.app_label
        response = HttpResponse(build_doc_file(app_label))
        response['Content-Disposition'] = 'attachment; filename="{}"'.format(doc_file_name(app_label))
        return response

    def docs_link(self, instance):
        return new_tab_link('{}/docs/'.format(instance.pk), label=doc_file_name(instance.model.app_label))

    docs_link.allow_tags = True
    docs_link.short_description = 'Documentation'
"""

def get_member_values(object, member_names, callable_flags):
    member_values = []
    for i in range(len(member_names)):
        member_name = member_names[i]
        is_callable = callable_flags[i]
        attr = getattr(object, member_name)
        if is_callable:
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
    app_labels = [app_label for app_label in app_labels if ptree.common.is_subsession_app(app_label)]
    apps = [{"name": app_name_format(app_label), "app_label": app_label} for app_label in app_labels]
    return render_to_response("admin/ptree_data_export_list.html", {"apps": apps})


@user_passes_test(lambda u: u.is_staff)
@login_required
def export_docs(request, app_label):
    #export = self.model.objects.get(pk=pk)
    #app_label = export.model.app_label
    response = HttpResponse(build_doc_file(app_label))
    response['Content-Disposition'] = 'attachment; filename="{}"'.format(doc_file_name(app_label))
    return response


@user_passes_test(lambda u: u.is_staff)
@login_required
def export(request, app_label):

    model_names_as_fk = {
        'match': 'Match',
        'treatment': 'Treatment',
        'subsession': 'Subsession',
        'session_participant': 'SessionParticipant',
        'session': 'Session',
    }

    format_name = "CSV"
    export_name = '{} participants'.format(app_label)

    app_models = import_module('{}.models'.format(app_label))

    Participant = app_models.Participant

    fk_names = [
        'match',
        'treatment',
        'subsession',
        'session_participant',
        'session',
    ]

    export_data = get_data_export_fields(app_label)

    parent_object_data = {fk_name:{} for fk_name in fk_names}

    column_headers = export_data['Participant']['member_names'][:]

    for fk_name in fk_names:
        model_name = model_names_as_fk[fk_name]
        member_names = export_data[model_name]['member_names']
        callable_flags = export_data[model_name]['callable_flags']
        column_headers += ['{}.{}'.format(fk_name, member_name) for member_name in member_names]

        # http://stackoverflow.com/questions/2466496/select-distinct-values-from-a-table-field#comment2458913_2468620
        ids = set(Participant.objects.order_by().values_list(fk_name, flat=True).distinct())
        if fk_name in {'session', 'session_participant'}:
            models_module = ptree.sessionlib.models
        else:
            models_module = app_models
        objects = getattr(models_module, model_name).objects.filter(pk__in=ids)

        for object in objects:

            parent_object_data[fk_name][object.id] = get_member_values(object, member_names, callable_flags)

    rows = [column_headers[:]]
    for participant in Participant.objects.all():
        member_names = export_data['Participant']['member_names'][:]
        callable_flags = export_data['Participant']['callable_flags'][:]
        member_values = get_member_values(participant, member_names, callable_flags)
        for fk_name in fk_names:
            parent_object_id = getattr(participant, "%s_id" % fk_name)
            member_values += parent_object_data[fk_name][parent_object_id]
        member_values = [unicode(v).encode('UTF-8') for v in member_values]
        print member_values
        rows.append(member_values)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="{} ({}).csv"'.format(ptree.common.app_name_format(app_label),
                                                                             datetime.date.today().isoformat())
    writer = csv.writer(response)

    writer.writerows(rows)

    return response
