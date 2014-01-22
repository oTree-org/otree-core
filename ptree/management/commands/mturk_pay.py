from django.core.management.base import BaseCommand, CommandError
from optparse import make_option
from django.conf import settings
from django.utils.importlib import import_module
import boto
from boto.mturk.connection import MTurkConnection
from boto.mturk.price import Price
from ptree.common import currency
import sys
from ptree.session.models import Session

def cents_to_dollars(num_cents):
    return round(num_cents/100.0,2)

class Command(BaseCommand):
    args = '<session_code>'
    help = "pTree: Pay all Mechanical Turk participants for this sequence of experiments."

    def handle(self, *args, **options):
        config = boto.config
        config.add_section('Credentials')

        AWS_ACCESS_KEY_ID = getattr(settings, 'AWS_ACCESS_KEY_ID')
        AWS_SECRET_ACCESS_KEY = getattr(settings, 'AWS_SECRET_ACCESS_KEY')

        if not AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY:
            print_function('You need to set your Amazon credentials in settings.py (AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY)')
            sys.exit(0)

        config.set('Credentials', 'aws_access_key_id', AWS_ACCESS_KEY_ID)
        config.set('Credentials', 'aws_secret_access_key', AWS_SECRET_ACCESS_KEY)

        config.add_section('boto')
        config.set('boto','https_validate_certificates', 'False')
        config.add_section('aws info')
        config.set('aws info','aws_validate_certs','False')

        if len(args) != 1:
            raise CommandError("Wrong number of arguments (expecting 'mturk_pay session code'. Example: 'mturk_pay motaliho')")
        else:
            session_code = args[0]

            self.connection = MTurkConnection(is_secure = True)

            self.session = Session.objects.get(code=session_code)
            if self.session.payment_was_sent:
                print 'Error: This experiment was already paid through pTree.'
                return

            if not (settings.CURRENCY_CODE == 'USD' and settings.CURRENCY_DECIMAL_PLACES == 2):
                print 'Error. CURRENCY_CODE must be set to USD and CURRENCY_DECIMAL_PLACES must be set to 2'
                return
            else:
                self.pay_hit_bonuses(is_confirmed=False)

                confirmed = raw_input('Enter "Y" to perform transaction:\n') == 'Y'
                if confirmed:
                    self.pay_hit_bonuses(is_confirmed=True)
                else:
                    print 'Exit. Did not pay bonuses.'
                    return
                print 'Done.'

    def pay_hit_bonuses(self, is_confirmed):

        total_money_paid = 0
        for participant in self.session.participants():
            bonus = participant.bonus()
            if bonus == None:
                bonus = 0
            total_money_paid += bonus

            if not is_confirmed:
                print 'Participant: [{}], Payment: {}'.format(participant.name, participant.bonus_display())
            if is_confirmed:
                if bonus > 0:
                    print bonus, Price(cents_to_dollars(bonus))
                    self.connection.grant_bonus(worker_id=participant.mturk_worker_id,
                                     assignment_id=participant.mturk_assignment_id,
                                     bonus_price = Price(cents_to_dollars(bonus)),
                                     reason='Thanks!')
        if not is_confirmed:
            print 'Total amount to pay: {}'.format(currency(total_money_paid))
        if is_confirmed:
            print 'Total amount paid: {}'.format(currency(total_money_paid))
            self.session.payment_was_sent = True
            self.session.save()