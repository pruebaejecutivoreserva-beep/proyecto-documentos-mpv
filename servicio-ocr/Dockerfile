FROM python:3.9-slim
WORKDIR /app
RUN apt-get update && apt-get install -y libglib2.0-0 libsm6 libxrender1 libxext6
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Forzamos a que use main.py y la variable app
CMD ["gunicorn", "--bind", ":8080", "--workers", "1", "--threads", "8", "--timeout", "0", "main:app"]
