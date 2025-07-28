FROM python:3.11-slim

# Use build arguments for flexibility
ARG PORT=8080
ENV PORT=${PORT}

# Working directory for app
WORKDIR /app

# Install dependencies first (for better caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose the port
EXPOSE ${PORT}

# Run with gunicorn for production
CMD gunicorn --workers=2 --threads=4 --timeout=120 --bind 0.0.0.0:${PORT} app:app
