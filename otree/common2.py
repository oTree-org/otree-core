# like common, but can import models
from otree.models_concrete import PageTimeBatch
import time
import otree.channels.utils as channel_utils

TIME_SPENT_COLUMNS = [
    'session_code',
    'participant_id_in_session',
    'participant_code',
    'page_index',
    'app_name',
    'page_name',
    'epoch_time',
    'round_number',
    'timeout_happened',
    'is_wait_page',
]


page_completion_buffer = []
page_completion_last_write = 0

BUFFER_SIZE = 50


def make_page_completion_row(
    *,
    view,
    app_name,
    participant__id_in_session,
    participant__code,
    session_code,
    is_wait_page,
):
    now = int(time.time())
    fields = dict(
        app_name=app_name,
        page_index=view._index_in_pages,
        page_name=type(view).__name__,
        epoch_time=now,
        round_number=view.round_number,
        participant_id_in_session=participant__id_in_session,
        participant_code=participant__code,
        session_code=session_code,
        timeout_happened=int(bool(getattr(view, 'timeout_happened', False))),
        is_wait_page=is_wait_page,
    )
    row = ','.join(str(fields[col]) for col in TIME_SPENT_COLUMNS) + '\n'

    page_completion_buffer.append(row)
    if (
        len(page_completion_buffer) > BUFFER_SIZE
        or now - page_completion_last_write > 60 * 2
    ):
        write_page_completion_buffer()


def write_page_completion_buffer():
    global page_completion_last_write
    PageTimeBatch.objects.create(text=''.join(page_completion_buffer))
    page_completion_last_write = time.time()
    page_completion_buffer.clear()
