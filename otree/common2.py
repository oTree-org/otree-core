# like common, but can import models
import time
from dataclasses import dataclass, asdict

from otree.database import db
from otree.models_concrete import PageTimeBatch


@dataclass
class TimeSpentRow:
    session_code: str
    participant_id_in_session: int
    participant_code: str
    page_index: int
    app_name: str
    page_name: str
    epoch_time_completed: int
    round_number: int
    timeout_happened: int
    is_wait_page: int


page_completion_buffer = []
page_completion_last_write = 0

BUFFER_SIZE = 50


def write_row_to_page_buffer(row: TimeSpentRow):
    d = asdict(row)
    row = ','.join(map(str, d.values())) + '\n'

    page_completion_buffer.append(row)
    if (
        len(page_completion_buffer) > BUFFER_SIZE
        or time.time() - page_completion_last_write > 60 * 2
    ):
        write_page_completion_buffer()


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
    row = TimeSpentRow(
        app_name=app_name,
        page_index=view._index_in_pages,
        page_name=type(view).__name__,
        epoch_time_completed=now,
        round_number=view.round_number,
        participant_id_in_session=participant__id_in_session,
        participant_code=participant__code,
        session_code=session_code,
        timeout_happened=int(bool(getattr(view, 'timeout_happened', False))),
        is_wait_page=is_wait_page,
    )
    write_row_to_page_buffer(row)


def write_page_completion_buffer():
    global page_completion_last_write
    db.add(PageTimeBatch(text=''.join(page_completion_buffer)))
    page_completion_last_write = time.time()
    page_completion_buffer.clear()
