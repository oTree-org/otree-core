from django.core.management.base import BaseCommand, CommandError
from optparse import make_option
from django.conf import settings
from django.utils.importlib import import_module
import boto
from boto.mturk.connection import MTurkConnection
from boto.mturk.price import Price
from ptree.templatetags.ptreefilters import currency

config = boto.config
config.add_section('Credentials')
config.set('Credentials', 'aws_access_key_id', settings.AWS_ACCESS_KEY_ID)
config.set('Credentials', 'aws_secret_access_key', settings.AWS_SECRET_ACCESS_KEY)

config.add_section('boto')
config.set('boto','https_validate_certificates', 'False')
config.add_section('aws info')
config.set('aws info','aws_validate_certs','False')

def cents_to_dollars(num_cents):
    return round(num_cents/100.0,2)

class Command(BaseCommand):
    help = "pTree: Pay all Mechanical Turk participants for this experiment."

    option_list = BaseCommand.option_list + (
        make_option('--app_label',
            type='str',
            dest='app_label',
            help='e.g. "dictator" or "ultimatum"'),

        make_option('--experiment_id',
            type='int',
            dest='experiment_id',
            help='The primary key of the experiment in the pTree database. e.g. "1" or "2"'),
    )

    def handle(self, *args, **options):
        app_label = options['app_label']
        experiment_id = options['experiment_id']
        self.connection = MTurkConnection(is_secure = True)
        models = import_module('{}.models'.format(app_label))
        self.experiment = models.Experiment.objects.get(id=experiment_id)
        if self.experiment.payment_was_sent:
            print 'This experiment was already paid through pTree.'
            print 'Abort.'
            return

        assert settings.CURRENCY_CODE == 'USD'
        assert settings.CURRENCY_DECIMAL_PLACES == 2
        self.pay_hit_bonuses(is_confirmed=False)

        confirmed = raw_input('Enter "Y" to perform transaction:\n') == 'Y'
        if confirmed:
            self.pay_hit_bonuses(is_confirmed=True)
        else:
            print 'Abort. Did not pay bonuses.'
        print 'Done.'

    def pay_hit_bonuses(self, is_confirmed):

        total_money_paid = 0
        for participant in self.experiment.participants():
            bonus = participant.safe_bonus()
            if bonus == None:
                bonus = 0
            total_money_paid += bonus

            if not is_confirmed:
                print 'Participant {}: {}'.format(participant.id, currency(bonus))
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
            self.experiment.payment_was_sent = True
            self.experiment.save()