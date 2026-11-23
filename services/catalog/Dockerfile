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

COPY services/catalog/requirements.txt /workspace/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY services/common /workspace/services/common
COPY services/catalog /workspace/services/catalog
COPY infra/docker/service-entrypoint.sh /workspace/service-entrypoint.sh
RUN chmod +x /workspace/service-entrypoint.sh

EXPOSE 8002

ENTRYPOINT ["/workspace/service-entrypoint.sh"]
CMD ["uvicorn", "services.catalog.app.main:app", "--host", "0.0.0.0", "--port", "8002"]
