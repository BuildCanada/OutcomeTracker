# --- Stage 1: Builder ---
# Use a stable base image for building our dependencies
FROM python:3.11-slim as builder

# Install system dependencies required for building some Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies into a virtual environment
# This will be copied to the final stage
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy only the requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Stage 2: Final Image ---
# Use a clean, lightweight base image for the final application
FROM python:3.11-slim as final

# Set working directory
WORKDIR /app

# Copy the virtual environment from the builder stage
COPY --from=builder /opt/venv /opt/venv

# Set the PATH environment variable to use the virtual environment's Python and packages
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Copy application code
# This is more specific than 'COPY . .' to improve caching.
COPY app ./app
COPY lib ./lib
COPY monitoring ./monitoring
COPY pipeline ./pipeline
COPY prompts ./prompts
COPY wsgi.py .
COPY .gcloudignore .
COPY cloudbuild.yaml .
COPY cloudbuild.base.yaml .
COPY package.json .
COPY tailwind.config.js .
COPY postcss.config.js .
COPY next-i18next.config.js .
COPY next.config.js .
COPY .dockerignore .
COPY Dockerfile.base .
COPY Dockerfile .
COPY babel.config.js .
COPY README.md .
COPY requirements.txt .
COPY tsconfig.json .

# Create non-root user for security
# Run as non-root user
RUN useradd -m -s /bin/bash -u 1001 appuser
RUN chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8080

# Run with Gunicorn for production
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "--timeout", "3600", "--preload", "wsgi:app"]