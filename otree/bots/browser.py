from .bot import ParticipantBot, Pause
from huey.contrib.djhuey import task, db_task
import json

# a dict holding all the browser bots
browser_bots = {}


def initialize_browser_bots(session):
    for participant in session.get_participants().filter(_is_bot=True):
        browser_bots[participant.code] = ParticipantBot(participant)


@db_task()
def get_next_submit(participant_code):
    bot = browser_bots[participant_code]
    try:
        while True:
            submit = next(bot.submits_generator)
            if isinstance(submit, Pause):
                # pauses are ignored when running browser bots,
                # because browser bots are for testing, not for real studies.
                # real studies should use regular bots
                continue
            else:
                return json.dumps(submit)
    except StopIteration:
        return
