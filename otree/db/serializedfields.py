from django.db import models
from six.moves import cPickle as pickle
import binascii
import six
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
        raise VarsError(
            "Cannot store '{}' object in vars. "
            "participant.vars and session.vars "
            "cannot contain model instances, "
            "like Players, Groups, etc.".format(repr(obj))
        )


def scan_for_model_instances(data):
    '''
    I don't know how to entirely block pickle from storing model instances,
    (I tried overriding __reduce__ but that interferes with deepcopy())
    so this simple shallow scan should be good enough.
    '''

    # vars should always be a dict
    if isinstance(data, dict):
        for k, v in data.items():
            inspect_obj(k)
            inspect_obj(v)
            if isinstance(v, dict):
                for kk, vv in v.items():
                    inspect_obj(kk)
                    inspect_obj(vv)
            elif isinstance(v, list):
                for ele in v:
                    inspect_obj(ele)


class _PickleField(six.with_metaclass(models.SubfieldBase, models.TextField)):
    """
    PickleField is a generic textfield that neatly serializes/unserializes
    any python objects seamlessly"""

    def to_python(self, value):
        """Convert our string value to JSON after we load it from the DB"""
        if value == "":
            return None

        try:
            if isinstance(value, six.string_types):
                return deserialize_from_string(value)
        except ValueError:
            pass

        return value

    def get_prep_value(self, value):
        """Convert our object to a string before we save"""
        if value == "" or value is None:
            return None

        scan_for_model_instances(value)
        value = serialize_to_string(value)
        value = force_text(value)
        return super().get_prep_value(value)
