# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV LIBRARY_PATH /data/manga-library
ENV CACHE_PATH /data/manga-cache
ENV DATABASE_URL sqlite+aiosqlite:////data/manga_dl.db

# Install system dependencies for curl-cffi and general utilities
RUN apt-get update && apt-get install -y \
    build-essential \
    libcurl4-openssl-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Create data directory for persistent storage (if volume is mounted)
RUN mkdir -p /data/manga-library /data/manga-cache

# Set work directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Expose port
EXPOSE 8080

# Command to run the application
# Cloud Run expects the app to listen on the port defined by the PORT environment variable
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
