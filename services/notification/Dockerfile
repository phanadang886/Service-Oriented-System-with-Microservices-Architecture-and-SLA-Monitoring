FROM python:3.11-slim

WORKDIR /workspace

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/workspace

COPY services/notification/requirements.txt /workspace/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY services/common /workspace/services/common
COPY services/notification /workspace/services/notification

EXPOSE 8004

CMD ["uvicorn", "services.notification.app.main:app", "--host", "0.0.0.0", "--port", "8004"]
