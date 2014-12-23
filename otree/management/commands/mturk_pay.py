#!/usr/bin/env python
# -*- coding: utf-8 -*-

# =============================================================================
# IMPORTS
# =============================================================================

import logging

from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from mturk import mturk

from otree.session.models import Session


logger = logging.getLogger(__name__)


def cents_to_dollars(num_cents):
    return round(num_cents / 100.0, 2)


class Command(BaseCommand):
    args = '<session_code>'
    help = "oTree: Pay all Mechanical Turk participants for this session."

    def handle(self, *args, **options):
        if len(args) != 1:
            raise CommandError("Wrong number of arguments (expecting "
                               "'mturk_pay session_code'. Example: "
                               "'mturk_pay motaliho')")

        try:
            config = {
                "use_sandbox": False,
                "stdout_log": True,
                "aws_key": settings.AWS_ACCESS_KEY_ID,
                "aws_secret_key": settings.AWS_SECRET_ACCESS_KEY,
            }
        except AttributeError:
            raise ImproperlyConfigured(
                'You need to set your Amazon credentials in settings.py '
                '(AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY)'
            )

        self.mturk_connection = mturk.MechanicalTurk(config)
        response = self.mturk_connection.request('GetAccountBalance')
        logger.info(response.get_response_element("AvailableBalance"))

        session_code = args[0]

        self.session = Session.objects.get(code=session_code)
        if self.session.mturk_payment_was_sent:
            raise CommandError(
                "This subsession was already paid through oTree."
            )

        if not (settings.PAYMENT_CURRENCY_CODE == 'USD' and
                settings.CURRENCY_DECIMAL_PLACES == 2):
            raise ImproperlyConfigured(
                'CURRENCY_CODE must be set to USD and '
                'CURRENCY_DECIMAL_PLACES must be set to 2'
            )
        else:
            self.pay_hit_bonuses(is_confirmed=False)

            confirmed = raw_input('Enter "Y" to perform transaction:\n') == 'Y'
            if confirmed:
                self.pay_hit_bonuses(is_confirmed=True)
            else:
                raise CommandError('Exit. Did not pay bonuses.')
            logger.info('Done.')

        response = self.mturk_connection.request('GetAccountBalance')
        logger.info(response.get_response_element("AvailableBalance"))

    def pay_hit_bonuses(self, is_confirmed):
        total_money_paid = 0
        for participant in self.session.get_participants():
            bonus = participant.payoff_from_subsessions()
            if bonus is None:
                bonus = 0
            total_money_paid += bonus

            if not is_confirmed:
                logger.info(
                    'Participant: [{}], Payment: {}'.format(
                        participant.name(),
                        participant.payoff_from_subsessions_display()
                    )
                )
            if is_confirmed:
                if bonus > 0:
                    self.mturk_connection.request(
                        'GrantBonus',
                        {
                            'WorkerId': participant.mturk_worker_id,
                            'AssignmentId': participant.mturk_assignment_id,
                            'BonusAmount': {
                                'Amount': str(cents_to_dollars(bonus)),
                                'CurrencyCode': 'USD'
                            },
                            'Reason': 'Thanks!',
                        }
                    )
        if not is_confirmed:
            logger.info('Total amount to pay: {}'.format(total_money_paid))
        if is_confirmed:
            logger.info('Total amount paid: {}'.format(total_money_paid))
            self.session.mturk_payment_was_sent = True
            self.session.save()
