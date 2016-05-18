from __future__ import absolute_import # for channels module
import asgi_redis
import redis.exceptions
import six
import sys
import os


class RedisChannelLayer(asgi_redis.RedisChannelLayer):
    def receive_many(self, channels, block=False):
        try:
            return super(RedisChannelLayer, self).receive_many(channels, block)
        except redis.exceptions.ConnectionError as exception:
            msg = (
                "oTree now requires Redis to be installed "
                "and running."
            )
            six.reraise(
                type(exception),
                type(exception)(msg + ' ' + str(exception)),
                sys.exc_info()[2])

    def new_channel(self, pattern):
        try:
            return super(RedisChannelLayer, self).new_channel(pattern)
        except redis.exceptions.ConnectionError as exception:
            msg = (
                "oTree now requires Redis to be installed "
                "and running."
            )
            six.reraise(
                type(exception),
                type(exception)(msg + ' ' + str(exception)),
                sys.exc_info()[2])
