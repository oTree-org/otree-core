from .utils import TestCase
import otree.session
from django.core.urlresolvers import reverse
import django.test
from otree.api import Currency
import otree.db.idmap

class TestPayoff(TestCase):



    def test_payoff(self):
        with self.settings(USE_POINTS=True):
            # Currency.DECIMAL_PLACES needs to be patched because the setting
            # is determined at startup, and does not change if you patch
            # USE_POINTS

            DECIMAL_PLACES_ORIGINAL_VALUE = Currency.DECIMAL_PLACES
            Currency.DECIMAL_PLACES = 2
            try:
                self.helper()
            finally:
                Currency.DECIMAL_PLACES = DECIMAL_PLACES_ORIGINAL_VALUE

    def helper(self):


        session = otree.session.create_session(
            session_config_name='two_rounds_1p',
            num_participants=1,
        )

        # need to activate cache after creating a session
        # because inside create_session, cache is deactivated
        otree.db.idmap.activate_cache()

        participant = session.participant_set.get(id=1)

        round_players = participant.get_players()

        round_payoff = Currency(13)

        round_players[0].payoff = round_payoff
        round_players[1].payoff = round_payoff

        otree.db.idmap.deactivate_cache()

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
