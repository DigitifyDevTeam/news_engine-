FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements/base.txt requirements/
RUN pip install --no-cache-dir -r requirements/base.txt

COPY engine/ /app/engine/

WORKDIR /app/engine

RUN playwright install chromium 2>/dev/null || true
RUN playwright install-deps chromium 2>/dev/null || true

EXPOSE 8000

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "engine.wsgi:application"]
