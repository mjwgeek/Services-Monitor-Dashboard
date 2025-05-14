#!/bin/bash
set -e

INSTALL_DIR="/home/servicemonitor"
VENV_DIR="$INSTALL_DIR/venv"

echo "🔄 Updating Service Monitor Dashboard..."

# Step 1: Check for local changes
cd "$INSTALL_DIR"
if ! git diff-index --quiet HEAD; then
    echo "[!] Local changes detected."
    echo "    - You can stash them with: git stash"
    echo "    - Or discard them with:    git reset --hard"
    echo "    - Skipping update."
    exit 1
fi

# Step 2: Pull latest changes
echo "[1] Pulling latest changes..."
git pull

# Step 3: Ensure virtual environment exists
if [ ! -d "$VENV_DIR" ]; then
    echo "[2] Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"

# Step 4: Reinstall dependencies in case requirements changed
echo "[3] Installing dependencies..."
"$VENV_DIR/bin/pip" install --no-cache-dir flask paramiko

# Step 5: Restart service
echo "[4] Restarting systemd service..."
sudo systemctl restart servicemonitor.service

echo "✅ Update complete!"
