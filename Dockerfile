# Main Dockerfile for the application
# --- IMPORTANT CHANGE ---
# Use your new, stable base image from your project's Artifact Registry.
FROM us-central1-docker.pkg.dev/promisetrackerapp/promise-tracker/promise-tracker-base:latest

# Set working directory
WORKDIR /app

# --- This step will now be CACHED because the base image is stable ---
# Copy requirements first for better caching
COPY requirements.txt .

# --- This step will also be CACHED unless requirements.txt changes ---
# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# --- This step will break the cache, which is what we want ---
# Copy the application code last
COPY . .

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Create non-root user for security
RUN useradd -m -u 1001 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8080

# Run with Gunicorn for production
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "--timeout", "3600", "--preload", "wsgi:app"]