FROM python:3.7.0-alpine3.7

RUN apk add --update alpine-sdk

WORKDIR /app
COPY requirements.txt ./
RUN pip install -r requirements.txt
COPY . .
