# TikTok Scrapper Docker Image
# Based on zendriver-docker approach for undetectable browser automation

FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    # Browser
    chromium \
    chromium-driver \
    # Display
    xvfb \
    x11vnc \
    fluxbox \
    # DBus (required for chromium)
    dbus \
    dbus-x11 \
    # Media processing
    ffmpeg \
    # Utilities
    wget \
    curl \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Set up display
ENV DISPLAY=:99
ENV CHROME_BIN=/usr/bin/chromium

# Create app directory
WORKDIR /app

# Copy requirements first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY *.py ./
COPY claude.md ./

# Create directories
RUN mkdir -p /app/output /app/downloads /app/browser_profile

# Entry script
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Expose VNC port for debugging
EXPOSE 5900

# Volume for output and browser profile persistence
VOLUME ["/app/output", "/app/browser_profile"]

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["python", "extract.py", "--help"]
