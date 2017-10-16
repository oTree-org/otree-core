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

    _pickle_fields = ['vars']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._save_the_change_store_initial_pickle_fields()

    def save(self, *args, **kwargs):
        self._save_the_change_check_pickle_field_changes()
        return super().save(*args, **kwargs)

    def _save_the_change_store_initial_pickle_fields(self):
        self._initial_prep_values = {}
        for field_name in self._pickle_fields:
            field = self._meta.get_field(field_name)
            self._initial_prep_values[field_name] = field.get_prep_value(
                getattr(self, field_name))

    def _save_the_change_check_pickle_field_changes(self):
        for field_name in self._pickle_fields:
            field = self._meta.get_field(field_name)
            new_value = field.get_prep_value(getattr(self, field_name))
            initial_prep_value = self._initial_prep_values[field_name]
            if new_value != initial_prep_value:
                self._changed_fields[field_name] = field.to_python(initial_prep_value)


class ModelWithVars(_SaveTheChangeWithCustomFieldSupport, models.Model):

    class Meta:
        abstract = True

    vars = models._PickleField(default=dict)  # type: dict
