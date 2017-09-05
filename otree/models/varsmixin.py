from otree.db import models

class _SaveTheChangeWithCustomFieldSupport:
    '''
    2017-08-07: kept around because old migrations files reference it.
    after a few months when i squash migrations,
    the references to this will be deleted, so i can delete it.

    2017-09-05: I found a bug with NumPy + SaveTheChange;
    https://github.com/karanlyons/django-save-the-change/issues/27
    So I need to use this again. Implementing a simplified version of what
    Gregor made a while back.
    '''


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._save_the_change_store_initial_vars()

    def save(self, *args, **kwargs):
        self._save_the_change_check_vars_changes()
        return super().save(*args, **kwargs)

    def _save_the_change_store_initial_vars(self):
        vars_field = self._meta.get_field('vars')
        self._vars_initial_prep_value = vars_field.get_prep_value(self.vars)

    def _save_the_change_check_vars_changes(self):
        vars_field = self._meta.get_field('vars')
        new_vars_value = vars_field.get_prep_value(self.vars)
        if new_vars_value != self._vars_initial_prep_value:
            self._changed_fields['vars'] = vars_field.to_python(self._vars_initial_prep_value)


class ModelWithVars(_SaveTheChangeWithCustomFieldSupport, models.Model):

    class Meta:
        abstract = True

    vars = models._PickleField(default=dict)  # type: dict
