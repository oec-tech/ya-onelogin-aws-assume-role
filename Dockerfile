FROM python:3.13-slim

WORKDIR /app
COPY . /app

RUN pip install --no-cache-dir awscli . \
    && mkdir -p /root/.onelogin \
    && if [ -f onelogin.sdk.json ]; then cp onelogin.sdk.json /root/.onelogin/; fi \
    && if [ -f config.yaml ]; then cp config.yaml /root/.onelogin/; fi

WORKDIR /root
