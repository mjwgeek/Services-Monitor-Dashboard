#!/bin/bash

set -e

# CONFIG
INSTALL_DIR="/home/servicemonitor"
REPO_URL="https://github.com/mjwgeek/servicemonitor.git"

# 1. Create installation directory
echo "[*] Creating install directory..."
sudo mkdir -p "$INSTALL_DIR"
sudo chown "$USER":"$USER" "$INSTALL_DIR"

# 2. Clone repository
echo "[*] Cloning Service Monitor repository..."
if [ -d "$INSTALL_DIR/.git" ]; then
  echo "[!] Repo already cloned. Skipping."
else
  git clone "$REPO_URL" "$INSTALL_DIR"
fi

cd "$INSTALL_DIR"

# 3. Install Python dependencies
echo "[*] Installing Python packages..."
pip3 install flask paramiko

# 4. Set permissions
chmod +x start_dashboard.sh

# 5. Install systemd services
echo "[*] Installing systemd service files..."
sudo cp systemd/system/*.service /etc/systemd/system/
sudo cp systemd/system/*.timer /etc/systemd/system/
sudo systemctl daemon-reexec

# 6. Enable and start services
echo "[*] Enabling services..."
sudo systemctl enable servicemonitor.service
sudo systemctl enable prefetch-services.timer
sudo systemctl start servicemonitor.service
sudo systemctl start prefetch-services.timer

echo "[✔] Install complete. Dashboard should be running at http://<your-ip>:8484"
