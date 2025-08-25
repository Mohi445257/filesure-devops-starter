FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt
COPY worker/ /app/worker/
EXPOSE 9100
# Worker processes one job then exits (KEDA-friendly)
CMD ["python", "worker/downloader.py"]
