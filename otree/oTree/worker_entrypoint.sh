#!/usr/bin/env bash

# wait for postgress to start
until /usr/bin/env python /opt/otree/otree/oTree/pg_ping.py 2>&1 >/dev/null; do
	echo 'wait for postgres to start...'
	sleep 5
done

echo 'running worker threads only...'
export PYTHONUNBUFFERED=1
cd /opt/otree/otree/oTree && otree collectstatic --noinput -v=3
cd /opt/otree/otree/oTree && otree runprodserver2of2
