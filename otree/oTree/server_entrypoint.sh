#!/usr/bin/env bash

# wait for postgress to start
until /usr/bin/env python /opt/otree/otree/oTree/pg_ping.py 2>&1 >/dev/null; do
	echo 'wait for postgres to start...'
	sleep 5
done

if [ ! -f "/opt/init/.done" ]; then
    /usr/bin/env python -u /usr/local/bin/otree resetdb --noinput -v 1 \
    && touch /opt/init/.done
fi

echo 'running main server threads only...'
export PYTHONUNBUFFERED=1
cd /opt/otree/otree/oTree && otree resetdb --noinput
cd /opt/otree/otree/oTree && otree collectstatic --noinput -v=3
cd /opt/otree/otree/oTree && otree runprodserver1of2 80
