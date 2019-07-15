FROM python:3.7.3-slim-stretch

ENV POETRY_VERSION='0.12.16'

RUN apt-get update \
    && apt-get install -y --no-install-recommends git gcc python-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install "poetry==${POETRY_VERSION}"

RUN mkdir /opt/app
WORKDIR /opt/app

COPY pyproject.toml poetry.lock ./
RUN poetry config settings.virtualenvs.create false && \
    poetry install --no-interaction

ENV PYTHONWARNINGS="ignore:Unverified HTTPS request"
ENV NODE_TLS_REJECT_UNAUTHORIZED=0
