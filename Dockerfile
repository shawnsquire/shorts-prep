FROM python:3.14-slim

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir flask gunicorn

WORKDIR /app
COPY app.py .

EXPOSE 8080
CMD ["gunicorn", "-b", "0.0.0.0:8080", "--timeout", "300", "--workers", "2", "app:app"]
