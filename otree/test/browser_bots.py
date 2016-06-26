from .client import ParticipantBot
from otree.models_concrete import BrowserBotSubmit

def store_submits_in_db(session):
    submit_models = []
    for participant in session.get_participants():
        participant_bot = ParticipantBot(participant)
        for player_bot in participant_bot.player_bots:
            # this appends the Submit objects
            # to participant_bot.submits
            player_bot.play_round()
        for submit in participant_bot.submits:
            submit_model = BrowserBotSubmit(
                session=session,
                participant=participant,
                page_dotted_name='{}.{}'.format(
                    submit.ViewClass.__module__,
                    submit.ViewClass.__name__
                ),
                param_dict=submit.data
            )
            submit_models.append(submit_model)
    BrowserBotSubmit.objects.bulk_create(submit_models)


