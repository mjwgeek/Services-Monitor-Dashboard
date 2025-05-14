#!/bin/bash
set -e

INSTALL_DIR="/home/servicemonitor"
VENV_DIR="$INSTALL_DIR/venv"
BACKUP_DIR="$INSTALL_DIR/backup/$(date +%Y%m%d-%H%M%S)"

echo "🔄 Updating Service Monitor Dashboard..."

# Step 1: Check for local changes
cd "$INSTALL_DIR"
if ! git diff-index --quiet HEAD; then
    echo "[!] Local changes detected."
    echo "    ➕ Backing up modified files to: $BACKUP_DIR"
    mkdir -p "$BACKUP_DIR"

    MODIFIED_FILES=$(git diff --name-only)
    for file in $MODIFIED_FILES; do
        if [ -f "$file" ]; then
            mkdir -p "$BACKUP_DIR/$(dirname $file)"
            mv "$file" "$BACKUP_DIR/$file"
            echo "    ✔ Moved: $file"
        fi
    done
fi

# Step 2: Pull latest changes
echo "[1] Pulling latest changes..."
git reset --hard
git pull

# Step 3: Ensure virtual environment exists
if [ ! -d "$VENV_DIR" ]; then
    echo "[2] Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"

# Step 4: Reinstall dependencies
echo "[3] Installing dependencies..."
"$VENV_DIR/bin/pip" install --no-cache-dir flask paramiko

# Step 5: Restart service
echo "[4] Restarting systemd service..."
sudo systemctl restart servicemonitor.service

echo "✅ Update complete!"
echo "📁 Your modified files were saved in: $BACKUP_DIR"
