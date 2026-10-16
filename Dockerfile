FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt server.py splitpay ./
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8000
CMD ["python", "server.py"]