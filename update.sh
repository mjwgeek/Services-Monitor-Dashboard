#!/bin/bash
set -e

INSTALL_DIR="/home/servicemonitor"
VENV_DIR="$INSTALL_DIR/venv"
BACKUP_DIR="$INSTALL_DIR/backups/$(date +%F-%H%M)"

echo "🔄 Updating Service Monitor Dashboard..."

cd "$INSTALL_DIR"

# Step 1: Detect changes
if ! git diff-index --quiet HEAD; then
    echo "📁 Local changes detected. Creating backup at $BACKUP_DIR"
    mkdir -p "$BACKUP_DIR"
    cp -r app.py templates "$BACKUP_DIR/"
    
    echo "⚠️  Resetting repo to latest state"
    git reset --hard
fi

# Step 2: Pull latest code
echo "[1] Pulling latest changes..."
git pull

# Step 3: Ensure virtualenv
if [ ! -d "$VENV_DIR" ]; then
    echo "[2] Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"

# Step 4: Install deps
echo "[3] Installing dependencies..."
"$VENV_DIR/bin/pip" install --no-cache-dir flask paramiko

# Step 5: Restart
echo "[4] Restarting systemd service..."
sudo systemctl restart servicemonitor.service

echo "✅ Update complete!"
