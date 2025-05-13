#!/bin/bash
set -e

# Configuration variables
INSTALL_DIR="/home/servicemonitor"
REPO_URL="https://github.com/mjwgeek/Services-Monitor-Dashboard.git"
SYSTEMD_DIR="/etc/systemd/system"

echo "🛠️ Starting Service Monitor installation..."

# 1. Check for Python 3 and install if missing
echo "[*] Checking for Python 3..."
if ! command -v python3 &> /dev/null; then
    echo "[!] Python 3 not found. Attempting to install..."
    sudo apt update
    sudo apt install -y python3 python3-pip
    if ! command -v python3 &> /dev/null; then
        echo "[ERROR] Failed to install Python 3. Please install it manually and run this script again."
        exit 1
    fi
    echo "[+] Python 3 installed successfully."
else
    echo "[+] Python 3 is already installed."
fi

# 2. Create installation directory
echo "[*] Creating directory: $INSTALL_DIR"
sudo mkdir -p "$INSTALL_DIR"
sudo chown "$USER":"$USER" "$INSTALL_DIR"

# 3. Clone repository
if [ -d "$INSTALL_DIR/.git" ]; then
    echo "[!] Repository already cloned to $INSTALL_DIR. Skipping clone."
else
    echo "[*] Cloning from $REPO_URL..."
    git clone "$REPO_URL" "$INSTALL_DIR"
fi
cd "$INSTALL_DIR"

# 4. Install Python dependencies
echo "[*] Installing Python packages (flask, paramiko)..."
pip3 install flask paramiko

# 5. Ensure nodes.json exists (empty list)
NODES_FILE="$INSTALL_DIR/nodes.json"
if [ ! -f "$NODES_FILE" ]; then
    echo "[*] Creating empty nodes.json..."
    echo "[]" > "$NODES_FILE"
else
    echo "[!] nodes.json already exists. Skipping."
fi

# 6. Install systemd service files
echo "[*] Installing systemd services..."
sudo cp systemd/system/.service "$SYSTEMD_DIR/"
sudo systemctl daemon-reexec
sudo systemctl daemon-reload

# 7. Enable and start main dashboard
echo "[*] Enabling and starting servicemonitor.service..."
sudo systemctl enable servicemonitor.service
sudo systemctl restart servicemonitor.service

# 8. Done
echo "✅ Installation complete."
echo "👉 Visit your dashboard at http://<your_server_ip>:8484"
