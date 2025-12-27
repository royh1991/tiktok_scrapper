#!/bin/bash
# TikTok Scrapper - Droplet Setup Script
# Run as: sudo bash setup.sh
#
# Tested on: Ubuntu 22.04 (DigitalOcean droplet)

set -e

echo "=== TikTok Scrapper Setup ==="

# Create user if not exists
if ! id -u tiktok &>/dev/null; then
    echo "Creating user 'tiktok'..."
    useradd -m -s /bin/bash tiktok
fi

# System dependencies
echo "Installing system packages..."
apt-get update
apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    ffmpeg \
    xvfb \
    x11vnc \
    xauth

# Install Chromium via snap (better TikTok compatibility)
echo "Installing Chromium..."
snap install chromium

# Create project directory
PROJECT_DIR="/home/tiktok/tiktok_scrapper"
echo "Setting up project at $PROJECT_DIR..."
mkdir -p "$PROJECT_DIR"
mkdir -p "$PROJECT_DIR/output"
mkdir -p "$PROJECT_DIR/browser_profiles"

# Create virtual environment
echo "Creating Python virtual environment..."
python3 -m venv "$PROJECT_DIR/venv"
source "$PROJECT_DIR/venv/bin/activate"

# Install Python dependencies
echo "Installing Python packages..."
pip install --upgrade pip
pip install \
    zendriver \
    aiohttp \
    aiofiles \
    httpx \
    anthropic \
    openai-whisper \
    opencv-python-headless \
    numpy \
    supabase \
    google-cloud-storage \
    python-dotenv \
    Pillow

# Set ownership
chown -R tiktok:tiktok "$PROJECT_DIR"

# Create .env template
if [ ! -f "$PROJECT_DIR/.env" ]; then
    cat > "$PROJECT_DIR/.env" << 'EOF'
# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-service-role-key

# Anthropic (for OCR)
ANTHROPIC_API_KEY=sk-ant-...

# Google Cloud Storage (optional)
GOOGLE_APPLICATION_CREDENTIALS=/home/tiktok/tiktok_scrapper/gcs-key.json
GCS_BUCKET=your-bucket-name
EOF
    chown tiktok:tiktok "$PROJECT_DIR/.env"
    echo "Created .env template - please edit with your credentials"
fi

# Create systemd service for Xvfb (virtual display for headless Chrome)
cat > /etc/systemd/system/xvfb.service << 'EOF'
[Unit]
Description=X Virtual Frame Buffer
After=network.target

[Service]
ExecStart=/usr/bin/Xvfb :99 -screen 0 1920x1080x24
Restart=always

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable xvfb
systemctl start xvfb

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "1. Copy your scripts to $PROJECT_DIR/"
echo "2. Edit $PROJECT_DIR/.env with your credentials"
echo "3. Switch to tiktok user: sudo su - tiktok"
echo "4. Activate venv: source ~/tiktok_scrapper/venv/bin/activate"
echo "5. Set display: export DISPLAY=:99"
echo "6. Run: python tiktok_downloader.py --help"
echo ""
