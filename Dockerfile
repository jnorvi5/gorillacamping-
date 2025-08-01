FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Use PORT environment variable provided by hosting platforms
ENV PORT=8080
EXPOSE 8080

CMD gunicorn --workers=2 --threads=4 --timeout=120 --bind 0.0.0.0:$PORT app:app
