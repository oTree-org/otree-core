import csv
import datetime

from django.http import HttpResponse
from django.conf import settings

import vanilla

import otree.common
import otree.models
import otree.export
from otree.models.participant import Participant
from otree.models.session import Session
from otree.extensions import get_extensions_data_export_views
from otree.models_concrete import ChatMessage


class ExportIndex(vanilla.TemplateView):

    template_name = 'otree/admin/Export.html'

    url_pattern = r"^export/$"

    def get_context_data(self, **kwargs):

        # can't use settings.INSTALLED_OTREE_APPS, because maybe the app
        # was removed from SESSION_CONFIGS.
        app_names_with_data = set()
        for session in Session.objects.all():
            for app_name in session.config['app_sequence']:
                app_names_with_data.add(app_name)

        custom_export_apps = []
        for app_name in app_names_with_data:
            models_module = otree.common.get_models_module(app_name)
            if getattr(models_module, 'custom_export', None):
                custom_export_apps.append(app_name)

        return super().get_context_data(
            db_is_empty=not Participant.objects.exists(),
            app_names=app_names_with_data,
            chat_messages_exist=ChatMessage.objects.exists(),
            extensions_views=get_extensions_data_export_views(),
            custom_export_apps=custom_export_apps,
            **kwargs,
        )


def get_csv_http_response(prefix) -> HttpResponse:
    response = HttpResponse(content_type='text/csv')
    date = datetime.date.today().isoformat()
    response['Content-Disposition'] = f'attachment; filename="{prefix}-{date}.csv"'
    return response


class ExportSessionWide(vanilla.View):
    '''used by data page'''

    url_pattern = r'^ExportSessionWide/(?P<session_code>[a-z0-9]+)/$'

    def get(self, request, session_code):
        response = get_csv_http_response('all_apps_wide')
        if bool(request.GET.get('excel')):
            # BOM
            response.write('\ufeff')
        otree.export.export_wide(response, session_code=session_code)
        return response


class ExportPageTimes(vanilla.View):

    url_pattern = r"^ExportPageTimes/$"

    def get(self, request):
        response = get_csv_http_response('PageTimes')
        otree.export.export_page_times(response)
        return response


class ExportChat(vanilla.View):

    url_pattern = '^otreechatcore_export/$'

    def get(self, request):
        response = get_csv_http_response('ChatMessages')
        column_names = [
            'participant__session__code',
            'participant__session_id',
            'participant__id_in_session',
            'participant__code',
            'channel',
            'nickname',
            'body',
            'timestamp',
        ]

        rows = ChatMessage.objects.order_by('timestamp').values_list(*column_names)

        writer = csv.writer(response)
        writer.writerows([column_names])
        writer.writerows(rows)

        return response
