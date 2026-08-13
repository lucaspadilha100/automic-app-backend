FROM python:3.12-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Create upload dir
RUN mkdir -p uploads

# Non-root user
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser
RUN chown -R appuser:appgroup /app
USER appuser

EXPOSE 8000

# Shell form so ${PORT} expands: Railway, Render and Fly assign the port at
# runtime and route only to that one. Falls back to 8000 for local `docker run`.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
