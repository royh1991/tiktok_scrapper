#!/bin/bash
# Setup script for DigitalOcean / Ubuntu server

set -e

echo "=== TikTok Scrapper Server Setup ==="

# Install system dependencies
echo "Installing system dependencies..."
sudo apt update
sudo apt install -y \
    ffmpeg \
    xvfb \
    chromium-browser \
    python3-pip \
    python3-venv

# Create virtual environment
echo "Setting up Python environment..."
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "=== Setup Complete ==="
echo ""
echo "To run extractions:"
echo "  source venv/bin/activate"
echo "  xvfb-run python extract.py -p 4 'url1,url2'"
echo ""
echo "IMPORTANT: You need to copy your browser_profile/ from local machine:"
echo "  scp -r browser_profile/ user@this-server:$(pwd)/"
echo ""
echo "Or log in via VNC:"
echo "  sudo apt install tigervnc-standalone-server"
echo "  vncserver :1"
echo "  export DISPLAY=:1"
echo "  python extract.py --login"
