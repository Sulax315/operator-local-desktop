FROM python:3.12-slim-bookworm

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
EXPOSE 8089

HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8089/health')"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8089"]
