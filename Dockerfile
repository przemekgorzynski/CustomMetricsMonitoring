FROM python:3.11-slim-buster@sha256:c46b0ae5728c2247b99903098ade3176a58e274d9c7d2efeaaab3e0621a53935

ARG PING_TARGETS
ARG DISK_TYPES_TO_MONITOR
ENV PING_TARGETS=${PING_TARGETS}
ENV DISK_TYPES_TO_MONITOR=${DISK_TYPES_TO_MONITOR}

RUN apt-get update -y && \
  apt-get install --no-install-recommends -y -q \
  libpq-dev python-dev build-essential libsnappy-dev && \
  apt-get clean && apt-get autoremove && \
  rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

WORKDIR /app

COPY python_scraper/custom_metrics.py .
COPY python_scraper/requirements.txt .

RUN pip install -r requirements.txt

EXPOSE 8000
CMD ["python", "/app/custom_metrics.py" ]
