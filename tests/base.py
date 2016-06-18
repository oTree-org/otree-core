#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.conf import settings
import django.test

import idmap.tls

# 2016-06-16: is this still needed? TODO
class OTreeTestClient(django.test.client.Client):

    def login(self):
        return super(OTreeTestClient, self).login(
            username=settings.ADMIN_USERNAME, password=settings.ADMIN_PASSWORD)


class TestCase(django.test.TestCase):

    client_class = OTreeTestClient
