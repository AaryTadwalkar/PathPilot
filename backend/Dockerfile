# ─── Backend Dockerfile ───────────────────────────────────────────────────────
# Base: Python 3.11 slim (matches local dev environment)
# Installs system libs needed for psycopg2, pgvector, and sentence-transformers
FROM python:3.11-slim

# Prevent interactive prompts during package install
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# System dependencies:
#   libpq-dev  -> psycopg2-binary native build
#   gcc / g++  -> sentence-transformers / numpy native extensions
#   git        -> some HF model downloads need it
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    g++ \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy and install Python dependencies first (layer-cached)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Download spacy model required by Module 1 (en_core_web_sm)
RUN python -m spacy download en_core_web_sm || true

# Copy the rest of the application code
COPY . .

# Expose FastAPI port
EXPOSE 8000

# Health check (gives postgres time to be ready)
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
