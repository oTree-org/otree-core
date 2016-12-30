#!/usr/bin/env python
# -*- coding: utf-8 -*-

import six


class BaseConstantsMeta(type):

    def __setattr__(cls, attr, value):
        raise AttributeError("Constants are read-only.")


class BaseConstants(six.with_metaclass(BaseConstantsMeta, object)):

    pass
