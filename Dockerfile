FROM python:3.7.7-slim

ENV REDIS_URL="redis://redis:6379" \
    DJANGO_SETTINGS_MODULE="settings"

ADD ./ /opt/otree

RUN apt-get update -y && apt-get install -y gcc libpq-dev

RUN pip install --no-cache-dir -r /opt/otree/requirements.txt
 
RUN pip install --no-cache-dir -e /opt/otree/.[server] \
    && mkdir -p /opt/init \
    && chmod +x /opt/otree/otree/oTree/server_entrypoint.sh \
    && chmod +x /opt/otree/otree/oTree/worker_entrypoint.sh 

RUN apt-get autoremove -y gcc

WORKDIR /opt/otree
VOLUME /opt/init
EXPOSE 80
