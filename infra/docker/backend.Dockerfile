FROM python:3.10-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1
COPY app/backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY app/backend /app/app/backend
COPY worker /app/worker
COPY data/seed /app/data/seed
ENV PYTHONPATH=/app/app/backend:/app
CMD ["uvicorn", "jogak_api.main:app", "--app-dir", "app/backend", "--host", "0.0.0.0", "--port", "8000"]
