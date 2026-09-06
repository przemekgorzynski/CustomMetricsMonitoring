FROM ubuntu:26.04

ARG PING_TARGETS=1.1.1.1,www.google.com
ARG DISK_TYPES_TO_MONITOR=sd,nvme
ARG DISK_DEVICES=
ENV PING_TARGETS=${PING_TARGETS}
ENV DISK_TYPES_TO_MONITOR=${DISK_TYPES_TO_MONITOR}
ENV DISK_DEVICES=${DISK_DEVICES}

RUN apt-get update -y && \
  apt-get install --no-install-recommends -y -q \
  python3 python3-venv zfsutils-linux ca-certificates && \
  apt-get clean && apt-get autoremove && \
  rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

WORKDIR /app

COPY python_scraper/custom_metrics.py .
COPY python_scraper/requirements.txt .

RUN python3 -m venv /venv && /venv/bin/pip install --no-cache-dir -r requirements.txt

EXPOSE 8000
CMD ["/venv/bin/python", "/app/custom_metrics.py" ]
