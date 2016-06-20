from .client import ParticipantBot
from otree.models_concrete import BrowserBotSubmit

def load_submits_to_db(session):
    submit_models = []
    for participant in session.get_participants():
        participant_bot = ParticipantBot(participant)
        for player_bot in participant_bot.player_bots:
            # this appends the Submit objects
            # to participant_bot.submits
            player_bot.play_round()
        for submit in participant_bot.submits:
            if submit.input_is_valid:
                submit_model = BrowserBotSubmit(
                    participant=participant,
                    page_name=submit.ViewClass.__name__,
                    param_dict=submit.data
                )
                submit_models.append(submit_model)
    BrowserBotSubmit.objects.bulk_create(submit_models)


