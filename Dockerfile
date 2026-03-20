# Use Python 3.13 slim image
FROM python:3.13-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONHASHSEED=random
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

# Create app directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    gfortran \
    libopenblas-dev \
    libpq-dev \
    build-essential \
    postgresql-client \
    postgresql-server-dev-all \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN python -m pip install --upgrade pip setuptools wheel && \
    python -m pip install -r requirements.txt

# Copy application code
COPY . .

# Set default dynamic port
ENV PORT=8000
EXPOSE ${PORT}

# Start the application using a shell to expand the $PORT variable
CMD uvicorn src.server.app:app --host 0.0.0.0 --port ${PORT}
