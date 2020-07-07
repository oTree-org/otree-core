import inspect
from django.db import models
import pickle
import binascii
from django.utils.encoding import force_text

__all__ = ('_PickleField',)


def serialize_to_string(data):
    """
    Dump arbitrary Python object `data` to a string that is base64 encoded
    pickle data.
    """
    return binascii.b2a_base64(pickle.dumps(data)).decode('utf-8')


def deserialize_from_string(data):
    return pickle.loads(binascii.a2b_base64(data.encode('utf-8')))


class VarsError(Exception):
    pass


def inspect_obj(obj):
    if isinstance(obj, models.Model):
        msg = (
            "Cannot store '{}' object in vars. "
            "participant.vars and session.vars "
            "cannot contain model instances, "
            "like Players, Groups, etc.".format(repr(obj))
        )
        raise VarsError(msg)


def scan_for_model_instances(vars_dict: dict):
    '''
    I don't know how to entirely block pickle from storing model instances,
    (I tried overriding __reduce__ but that interferes with deepcopy())
    so this simple shallow scan should be good enough.
    '''

    for v in vars_dict.values():
        inspect_obj(v)
        if isinstance(v, dict):
            for vv in v.values():
                inspect_obj(vv)
        elif isinstance(v, list):
            for ele in v:
                inspect_obj(ele)


class _PickleField(models.TextField):
    """
    PickleField is a generic textfield that serializes/unserializes
    any nested dict"""

    def to_python(self, value):
        return deserialize_from_string(value)

    def get_prep_value(self, value):
        """Convert our object to a string before we save"""
        if not isinstance(value, dict):
            type_name = type(value).__name__
            model_instance_name = self.model.__name__.lower()
            field_name = self.name
            msg = (
                f'{model_instance_name}.{field_name} must be a dict, not {type_name}. '
            )
            raise ValueError(msg)

        scan_for_model_instances(value)
        value = serialize_to_string(value)
        return force_text(value)

    def from_db_value(self, value, expression, connection):
        return self.to_python(value)
