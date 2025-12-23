#!/bin/bash
set -e

echo "=== TikTok Scrapper Docker ==="

# Start dbus
mkdir -p /run/dbus
dbus-daemon --system --fork 2>/dev/null || true

# Start Xvfb (virtual display)
echo "Starting virtual display..."
Xvfb :99 -screen 0 1920x1080x24 &
sleep 2

# Start a simple window manager (suppress warnings)
fluxbox 2>/dev/null &
sleep 1

# Optionally start VNC for debugging (if VNC_ENABLED is set)
if [ "${VNC_ENABLED:-false}" = "true" ]; then
    echo "Starting VNC server on port 5900..."
    x11vnc -display :99 -forever -nopw -quiet 2>/dev/null &
    echo "VNC available at localhost:5900"
fi

echo "Display ready: $DISPLAY"
echo ""

# Clear stale browser singleton files (from previous container runs)
rm -f /app/browser_profile/Singleton* 2>/dev/null || true

# Run the command
exec "$@"
