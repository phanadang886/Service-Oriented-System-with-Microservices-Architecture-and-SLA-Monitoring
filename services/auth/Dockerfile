FROM python:3.11-slim

WORKDIR /workspace

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/workspace

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY services/auth/requirements.txt /workspace/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY services/common /workspace/services/common
COPY services/auth /workspace/services/auth

EXPOSE 8001

CMD ["uvicorn", "services.auth.app.main:app", "--host", "0.0.0.0", "--port", "8001"]
