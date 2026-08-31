FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Run build script for static files
RUN chmod +x build.sh && ./build.sh

EXPOSE 8000

CMD ["gunicorn", "prediction_platform.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
