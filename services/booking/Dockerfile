FROM python:3.11-slim

WORKDIR /workspace

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/workspace

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Alembic + psycopg run inside the container so migrations apply on startup.
COPY requirements-dev.txt /workspace/requirements-dev.txt
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY services/booking/requirements.txt /workspace/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY services/booking /workspace/services/booking
COPY infra/docker/service-entrypoint.sh /workspace/service-entrypoint.sh
RUN chmod +x /workspace/service-entrypoint.sh

EXPOSE 8003

ENTRYPOINT ["/workspace/service-entrypoint.sh"]
CMD ["uvicorn", "services.booking.app.main:app", "--host", "0.0.0.0", "--port", "8003"]
