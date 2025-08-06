# Base image with uv and Python installed
FROM ghcr.io/astral-sh/uv:debian

# Set working directory inside the container
WORKDIR /app

# Install system dependencies for building Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    supervisor \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY . .

# Copy entrypoint script
COPY entrypoint.sh /app/entrypoint.sh

# Expose port for Flask (default 5000)
EXPOSE 5000

ENTRYPOINT ["/app/entrypoint.sh"]
