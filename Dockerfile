FROM python:3.11-slim@sha256:da047cb8f9d1d98e5c070f5300ba9f7274e33b8fc0e5be5ed88740aed1b95ba9

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY scripts ./scripts
COPY config ./config
COPY init.sql ./init.sql

EXPOSE 8000

CMD ["sh", "-c", "python scripts/migrate.py && uvicorn app.main:app --host 0.0.0.0 --port 8000 --ws-max-size 16384"]
