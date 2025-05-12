#!/bin/bash

set -e

# CONFIGURATION
INSTALL_DIR="/home/servicemonitor"
REPO_URL="https://github.com/mjwgeek/Services-Monitor-Dashboard.git"
SYSTEMD_DIR="/etc/systemd/system"

echo "🛠  Starting Service Monitor installation..."

# 1. Create installation directory
echo "[*] Creating directory: $INSTALL_DIR"
sudo mkdir -p "$INSTALL_DIR"
sudo chown "$USER":"$USER" "$INSTALL_DIR"

# 2. Clone repository
if [ -d "$INSTALL_DIR/.git" ]; then
  echo "[!] Repository already cloned to $INSTALL_DIR. Skipping clone."
else
  echo "[*] Cloning from $REPO_URL..."
  git clone "$REPO_URL" "$INSTALL_DIR"
fi

cd "$INSTALL_DIR"

# 3. Install Python dependencies
echo "[*] Installing Python packages (flask, paramiko)..."
pip3 install flask paramiko

# 4. Make sure startup script is executable
chmod +x start_dashboard.sh

# 5. Ensure nodes.json exists (empty list)
NODES_FILE="$INSTALL_DIR/nodes.json"
if [ ! -f "$NODES_FILE" ]; then
  echo "[*] Creating empty nodes.json..."
  echo "[]" > "$NODES_FILE"
else
  echo "[!] nodes.json already exists. Skipping."
fi

# 6. Remove obsolete prefetch-timer.service if it exists
if [ -f "$SYSTEMD_DIR/prefetch-timer.service" ]; then
  echo "[*] Removing legacy prefetch-timer.service..."
  sudo systemctl stop prefetch-timer.service || true
  sudo systemctl disable prefetch-timer.service || true
  sudo rm -f "$SYSTEMD_DIR/prefetch-timer.service"
fi

# 7. Install systemd service files
echo "[*] Installing systemd services..."
sudo cp systemd/system/*.service "$SYSTEMD_DIR/"
sudo systemctl daemon-reexec
sudo systemctl daemon-reload

# 8. Enable and start main dashboard
echo "[*] Enabling and starting servicemonitor.service..."
sudo systemctl enable servicemonitor.service
sudo systemctl restart servicemonitor.service

# 9. Done
echo "✅ Installation complete."
echo "👉 Visit your dashboard at http://<your-ip>:8484"
