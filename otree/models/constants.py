#!/usr/bin/env python
# -*- coding: utf-8 -*-


class BaseConstantsMeta(type):

    def __setattr__(cls, attr, value):
        msg = "can't set attribute '{}'".format(attr)
        raise AttributeError(msg)


class BaseConstants(object):

    __metaclass__ = BaseConstantsMeta
