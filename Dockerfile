FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5001

# Usamos gunicorn con 4 workers y 4 threads para soportar concurrencia en el benchmark
CMD ["gunicorn", "--bind", "0.0.0.0:5001", "--workers", "4", "--threads", "4", "--timeout", "60", "app:app"]
