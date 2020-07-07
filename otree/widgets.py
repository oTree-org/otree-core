# We moved the otree.widgets module to otree.forms.widgets
# prior to adding otree.api in September 2016, each models.py contained:
# "from otree import widgets"

from logging import getLogger

logger = getLogger(__name__)

MSG_NEW_IMPORTS = '''
otree.widgets does not exist anymore. You should update your imports in models.py to:

from otree.api import (
    models, widgets, BaseConstants, BaseSubsession, BaseGroup, BasePlayer,
    Currency as c, currency_range
)
'''

logger.warning(MSG_NEW_IMPORTS)

from .forms.widgets import *
