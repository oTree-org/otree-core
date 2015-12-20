import copy
from otree_save_the_change.mixins import SaveTheChange

from otree.db import models


class ModelWithVars(SaveTheChange, models.Model):
    vars = models.JSONField(default=dict)

    class Meta:
        abstract = True

    def __init__(self, *args, **kwargs):
        super(ModelWithVars, self).__init__(*args, **kwargs)
        self._old_vars = copy.deepcopy(self.vars)

    def _vars_have_changed(self):
        return self.vars != self._old_vars

    def save(self, *args, **kwargs):
        # Trick otree_save_the_change to update vars
        if hasattr(self, '_changed_fields') and self._vars_have_changed():
            self._changed_fields['vars'] = self._old_vars
        super(ModelWithVars, self).save(*args, **kwargs)
