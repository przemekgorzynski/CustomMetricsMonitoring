FROM python:3.11.8-alpine3.19

ARG PING_TARGETS
ENV PING_TARGETS=${PING_TARGETS}

WORKDIR /app

COPY python_scraper/custom_metrics.py .
COPY python_scraper/requirements.txt .

RUN pip install -r requirements.txt

EXPOSE 8000
CMD [ "python", "/app/custom_metrics.py" ]
