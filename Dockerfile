FROM python:3.12

COPY \
  requirements.txt /etc/

RUN \
  pip install --upgrade pip && \
  pip install -r /etc/requirements.txt

ENV PYTHONPATH="${PYTHONPATH}:/opt/tests"

WORKDIR /opt/tests
