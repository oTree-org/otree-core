from io import StringIO
import csv
import datetime

from starlette.responses import Response
from starlette.endpoints import HTTPEndpoint
from . import cbv

import otree.common
import otree.models
import otree.export
from otree.export import BOM, get_installed_apps_with_data
from otree.models.participant import Participant
from otree.models.session import Session
from otree.models_concrete import ChatMessage
from otree.database import dbq


class Export(cbv.AdminView):
    url_pattern = '/export'

    def vars_for_template(self):

        # can't use settings.OTREE_APPS, because maybe the app
        # was removed from SESSION_CONFIGS.
        app_names_with_data = get_installed_apps_with_data()

        custom_export_apps = []
        for app_name in app_names_with_data:
            models_module = otree.common.get_models_module(app_name)
            if getattr(models_module, 'custom_export', None):
                custom_export_apps.append(app_name)

        return dict(
            db_is_empty=not bool(dbq(Participant).first()),
            app_names=app_names_with_data,
            chat_messages_exist=bool(dbq(ChatMessage).first()),
            custom_export_apps=custom_export_apps,
        )


def get_csv_http_response(buffer: StringIO, filename_prefix) -> Response:
    buffer.seek(0)
    response = Response(buffer.read())
    date = datetime.date.today().isoformat()
    response.headers['Content-Type'] = 'text/csv'
    response.headers[
        'Content-Disposition'
    ] = f'attachment; filename="{filename_prefix}-{date}.csv"'
    return response


class ExportSessionWide(HTTPEndpoint):
    '''used by data page'''

    url_pattern = '/ExportSessionWide/{code}'

    def get(self, request):
        code = request.path_params['code']
        # we can't use AUTH_LEVEL to guard this, since it should ideally
        # be available in demo mode. (so that the UI can be consistent,
        # and it's also a good feature to demo oTree)
        if request.query_params.get('token') != otree.common.DATA_EXPORT_HASH:
            return Response(status_code=400, content="Missing or incorrect auth token")
        buf = StringIO()
        if bool(request.query_params.get('excel')):
            # BOM
            buf.write(BOM)
        otree.export.export_wide(buf, session_code=code)
        return get_csv_http_response(buf, 'all_apps_wide')


class ExportPageTimes(HTTPEndpoint):

    url_pattern = '/ExportPageTimes'

    def get(self, request):
        buf = StringIO()
        otree.export.export_page_times(buf)
        response = get_csv_http_response(buf, 'PageTimes')
        return response


class ExportChat(HTTPEndpoint):

    url_pattern = '/chat_export'

    def get(self, request):
        buf = StringIO()
        column_names = [
            'session_code',
            'id_in_session',
            'participant_code',
            'channel',
            'nickname',
            'body',
            'timestamp',
        ]

        rows = (
            dbq(ChatMessage)
            .join(Participant)
            .order_by(ChatMessage.timestamp)
            .with_entities(
                Participant._session_code,
                Participant.id_in_session,
                Participant.code,
                ChatMessage.channel,
                ChatMessage.nickname,
                ChatMessage.body,
                ChatMessage.timestamp,
            )
        )

        writer = csv.writer(buf)
        writer.writerows([column_names])
        writer.writerows(rows)
        response = get_csv_http_response(buf, 'ChatMessages')
        return response
