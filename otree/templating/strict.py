class VariableDoesNotExist(Exception):
    pass


class OtreeUndefined:

    """ Null type returned when a context lookup fails. """

    def __str__(self):
        raise VariableDoesNotExist

    def __bool__(self):
        raise VariableDoesNotExist

    def __len__(self):
        raise VariableDoesNotExist

    def __contains__(self, key):
        raise VariableDoesNotExist

    def __iter__(self):
        raise VariableDoesNotExist

    def __next__(self):
        raise VariableDoesNotExist

    def __eq__(self, other):
        raise VariableDoesNotExist

    def __ne__(self, other):
        raise VariableDoesNotExist
