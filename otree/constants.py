class BaseConstantsMeta(type):
    def __setattr__(cls, attr, value):
        raise AttributeError("Constants are read-only.")


class BaseConstants(metaclass=BaseConstantsMeta):
    pass
