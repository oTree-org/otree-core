import babel.numbers
from django.conf import settings
from decimal import Decimal
import urllib
import urlparse
from django.utils.importlib import import_module
import subprocess

def add_params_to_url(url, params):
    url_parts = list(urlparse.urlparse(url))
    query = dict(urlparse.parse_qsl(url_parts[4]))
    query.update(params)
    url_parts[4] = urllib.urlencode(query)
    return urlparse.urlunparse(url_parts)

def id_label_name(id, label):
    if label:
        return '{} (label: {})'.format(id, label)
    return '{}'.format(id)

def currency(value):
    """Takes in a number of cents (int) and returns a formatted currency amount.
    """

    if value == None:
        return '?'
    value_in_major_units = Decimal(value)/(10**settings.CURRENCY_DECIMAL_PLACES)
    return babel.numbers.format_currency(value_in_major_units, settings.CURRENCY_CODE, locale=settings.CURRENCY_LOCALE)

def create_match(MatchClass, treatment):
    match = MatchClass(treatment = treatment,
                       experiment = treatment.experiment,
                       session = treatment.session)
    # need to save it before you assign the participant.match ForeignKey
    match.save()
    return match

def add_participant_to_existing_match(participant, match):
    participant.index_among_participants_in_match = match.participants().count()
    participant.match = match

def assign_participant_to_match(MatchClass, participant):
    if not participant.match:
        match = participant.treatment.next_open_match() or create_match(MatchClass, participant.treatment)
        add_participant_to_existing_match(participant, match)

def is_experiment_app(app_label):
    try:
        models_module = import_module('{}.models'.format(app_label))
    except ImportError:
        return False
    class_names = ['Participant', 'Match', 'Treatment', 'Experiment']
    return all(hasattr(models_module, ClassName) for ClassName in class_names)

def git_hash():
    try:
        hash = subprocess.check_output(['git rev-parse HEAD'.split()])
    except:
        return None
    try:
        subprocess.check_call('git diff-index --quiet HEAD')
        return hash
    except subprocess.CalledProcessError:
        return '{} (plus uncommitted changes)'.format(hash)

