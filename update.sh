#!/bin/bash
set -e

INSTALL_DIR="/home/servicemonitor"
VENV_DIR="$INSTALL_DIR/venv"
BACKUP_DIR="$INSTALL_DIR/backups/$(date +%F-%H%M)"

echo "🔄 Updating Service Monitor Dashboard..."

cd "$INSTALL_DIR"

# Step 1: Detect local changes
if ! git diff-index --quiet HEAD; then
    echo "📁 Local changes detected. Creating backup at $BACKUP_DIR"
    mkdir -p "$BACKUP_DIR"
    cp -r app.py templates nodes.json "$BACKUP_DIR/" 2>/dev/null || true
    echo "⚠️  Resetting repo to latest state"
    git reset --hard
fi

# Step 2: Pull latest code
echo "[1] Pulling latest changes..."
git pull

# Step 3: Ensure virtual environment
if [ ! -d "$VENV_DIR" ]; then
    echo "[2] Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"

# Step 4: Install updated Python dependencies
echo "[3] Installing/updating dependencies..."
"$VENV_DIR/bin/pip" install --no-cache-dir \
    flask \
    flask-socketio \
    eventlet \
    paramiko

# Step 5: Restart the systemd service
echo "[4] Restarting servicemonitor.service..."
sudo systemctl restart servicemonitor.service

echo "✅ Update complete!"
