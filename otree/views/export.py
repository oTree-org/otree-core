import datetime

from django.http import HttpResponse
from django.conf import settings

import vanilla

import otree.common_internal
import otree.models
from otree.common_internal import app_name_format
import otree.export
from otree.models.participant import Participant
from otree.extensions import get_extensions_data_export_views


class ExportIndex(vanilla.TemplateView):

    template_name = 'otree/admin/Export.html'

    url_pattern = r"^export/$"

    def get_context_data(self, **kwargs):
        context = super(ExportIndex, self).get_context_data(**kwargs)

        context['db_is_empty'] = not Participant.objects.exists()

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
        context['apps'] = apps

        context['extensions_views'] = get_extensions_data_export_views()

        return context


class ExportAppDocs(vanilla.View):

    url_pattern = r"^ExportAppDocs/(?P<app_label>[\w.]+)/$"

    def _doc_file_name(self, app_label):
        return '{} - documentation ({}).txt'.format(
            otree.common_internal.app_name_format(app_label),
            datetime.date.today().isoformat()
        )

    def get(self, request, *args, **kwargs):
        app_label = kwargs['app_label']
        response = HttpResponse(content_type='text/plain')
        response['Content-Disposition'] = 'attachment; filename="{}"'.format(
            self._doc_file_name(app_label)
        )
        otree.export.export_docs(response, app_label)
        return response


def get_export_response(request, file_prefix):
    if bool(request.GET.get('xlsx')):
        content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        file_extension = 'xlsx'
    else:
        content_type = 'text/csv'
        file_extension = 'csv'
    response = HttpResponse(
        content_type=content_type)
    response['Content-Disposition'] = 'attachment; filename="{}"'.format(
        '{} (accessed {}).{}'.format(
            file_prefix,
            datetime.date.today().isoformat(),
            file_extension
        ))
    return response, file_extension


class ExportApp(vanilla.View):

    url_pattern = r"^ExportApp/(?P<app_label>[\w.]+)/$"

    def get(self, request, *args, **kwargs):

        app_label = kwargs['app_label']
        response, file_extension = get_export_response(request, app_label)
        otree.export.export_app(app_label, response, file_extension=file_extension)
        return response


class ExportWide(vanilla.View):

    url_pattern = r"^ExportWide/$"

    def get(self, request, *args, **kwargs):
        response, file_extension = get_export_response(
            request, 'All apps - wide')
        otree.export.export_wide(response, file_extension)
        return response


class ExportTimeSpent(vanilla.View):

    url_pattern = r"^ExportTimeSpent/$"

    def get(self, request, *args, **kwargs):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="{}"'.format(
            'TimeSpent (accessed {}).csv'.format(
                datetime.date.today().isoformat()
            )
        )
        otree.export.export_time_spent(response)
        return response
