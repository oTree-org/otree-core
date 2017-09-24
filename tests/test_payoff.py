from .utils import TestCase
import otree.session
from django.core.urlresolvers import reverse
import django.test
from otree.api import Currency
import otree.db.idmap
from django.test import override_settings


class TestPayoff(TestCase):

    def test_participant_payoff(self):
        '''Should be able to set participant.payoff directly'''
        session = otree.session.create_session(
            session_config_name='two_rounds_1p',
            num_participants=1,
        )

        payoff = Currency(10)

        participant = session.participant_set.first()
        participant.payoff = payoff
        participant.save()

        participant = session.participant_set.first()
        self.assertEqual(participant.payoff, payoff)

    @override_settings(USE_POINTS=True, POINTS_DECIMAL_PLACES=2)
    def test_payoff(self):

        session = otree.session.create_session(
            session_config_name='two_rounds_1p',
            num_participants=1,
        )

        # need to activate cache after creating a session
        # because inside create_session, cache is deactivated
        with otree.db.idmap.use_cache():

            # for some reason id=1 test fails, because the session only has
            # participant with id=2. ah, that makes sense. even if the DB
            # is truncated, PKs will still be incremented, i think.
            participant = session.participant_set.first()

            round_players = participant.get_players()

            round_payoff = Currency(13)

            round_players[0].payoff = round_payoff
            round_players[1].payoff = round_payoff

        payoff = participant.payoff
        self.assertEqual(payoff, 2*round_payoff)

        participation_fee = session.config['participation_fee']
        self.assertEqual(participation_fee, 1.25)

        real_world_currency_per_point = session.config['real_world_currency_per_point']
        self.assertEqual(real_world_currency_per_point, 0.5)

        payoff_in_real_world_currency = payoff * real_world_currency_per_point

        payoff_plus_participation_fee = participant.payoff_plus_participation_fee()

        self.assertEqual(
            payoff_plus_participation_fee,
            payoff_in_real_world_currency + participation_fee)

        payments_url = reverse('SessionPayments', args=[session.code])

        client = django.test.Client()
        resp = client.get(payments_url)
        html = resp.content.decode('utf-8')
        for amount in [
            '\u20ac1.25', # participation fee
            '\u20ac13.00', # participant.payoff
            '\u20ac14.25' # base plus participant.payoff
        ]:
            self.assertIn(amount, html)
