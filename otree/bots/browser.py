from .bot import ParticipantBot, Pause, submission_as_dict
from huey.contrib.djhuey import task, db_task
import json
from otree.models import Session

# a dict holding all the browser bots
browser_bots = {}


@db_task()
def initialize_browser_bots(session_code):
    session = Session.objects.get(code=session_code)
    for participant in session.get_participants().filter(_is_bot=True):
        browser_bots[participant.code] = ParticipantBot(participant)


@task()
def clear_browser_bots():
    browser_bots.clear()


@db_task()
def get_next_submit(participant_code):
    try:
        bot = browser_bots[participant_code]
    except KeyError:
        print('no browser bot with code {}'.format(participant_code))
    try:
        import random
        r = random.random()
        while True:
            submit = next(bot.submits_generator)

            if isinstance(submit, Pause):
                # pauses are ignored when running browser bots,
                # because browser bots are for testing, not for real studies.
                # real studies should use regular bots
                continue
            else:
                submission = json.dumps(submission_as_dict(submit))
                return submission
    except StopIteration:
        # clear from global var
        browser_bots.pop(participant_code, None)
        return
