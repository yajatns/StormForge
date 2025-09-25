# StormForge Traffic Orchestrator
# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    hping3 \
    curl \
    wget \
    git \
    sqlite3 \
    build-essential \
    pkg-config \
    libcairo2-dev \
    libgirepository1.0-dev \
    sudo \
    && rm -rf /var/lib/apt/lists/*

# Create application user
RUN useradd --create-home --shell /bin/bash --uid 1000 stormforge

# Set capabilities for hping3
RUN setcap cap_net_raw=eip /usr/sbin/hping3

# Create application directory
WORKDIR /app

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Install Node.js for frontend building
RUN curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - && \
    apt-get install -y nodejs

# Copy application code
COPY . .

# Build frontend
RUN cd frontend && npm install && npm run build

# Create necessary directories
RUN mkdir -p logs data config && \
    chown -R stormforge:stormforge /app

# Switch to non-root user
USER stormforge

# Create default environment file
RUN if [ ! -f .env ]; then \
    echo "DATABASE_URL=sqlite:///./data/orchestrator.db" > .env && \
    echo "SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')" >> .env && \
    echo "JWT_SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')" >> .env && \
    echo "HOST=0.0.0.0" >> .env && \
    echo "PORT=8000" >> .env && \
    echo "DEBUG=false" >> .env; \
    fi

# Initialize database
RUN python3 -c "
from app.database import engine, Base
from app.models import User, Job, TargetGroup, APIKey, AuditLog, Quota
Base.metadata.create_all(bind=engine)
"

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]