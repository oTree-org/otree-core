# -*- coding: utf-8 -*-
import psycopg2
import sys

from django.db import connections

try:
    print(connections)
    connection = psycopg2.connect(database=connections['default'].settings_dict['NAME'],
                                  user=connections['default'].settings_dict['USER'],
                                  password=connections['default'].settings_dict['PASSWORD'],
                                  host=connections['default'].settings_dict['HOST'],
                                  port=connections['default'].settings_dict['PORT'])
except psycopg2.OperationalError as e:
    str = "{}, {}, {}, {}, {}, {}".format(
        connections,
        connections['default'].settings_dict['NAME'],
        connections['default'].settings_dict['USER'],
        connections['default'].settings_dict['PASSWORD'],
        connections['default'].settings_dict['HOST'],
        connections['default'].settings_dict['PORT'])
    sys.exit("{}: The database is not ready. {}".format(e, str))
