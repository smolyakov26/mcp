FROM python:3.12-slim

WORKDIR /app
COPY server.py .

RUN pip install --no-cache-dir fastapi uvicorn psycopg2-binary requests
    