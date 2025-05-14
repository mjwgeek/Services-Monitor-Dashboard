#!/bin/bash
set -e

# Configuration variables
INSTALL_DIR="/home/servicemonitor"
REPO_URL="https://github.com/mjwgeek/Services-Monitor-Dashboard.git"
SYSTEMD_DIR="/etc/systemd/system"
VENV_DIR="$INSTALL_DIR/venv"

echo "🛠️ Starting Service Monitor installation..."

# Step 1. Check for Python 3 and install if missing
echo "[1] Checking for Python 3..."
if ! command -v python3 &> /dev/null; then
    echo "[!] Python 3 not found. Attempting to install..."
    sudo apt update
    sudo apt install -y python3 python3-pip python3-venv
else
    echo "[+] Python 3 is already installed."
fi

# Step 1a. Ensure python3-venv is installed (even if Python is present)
echo "[1a] Ensuring python3-venv is installed..."
if ! dpkg -s python3-venv &> /dev/null; then
    echo "[*] Installing python3-venv..."
    sudo apt install -y python3-venv
else
    echo "[+] python3-venv is already installed."
fi

# Step 2. Create installation directory
echo "[2] Creating directory: $INSTALL_DIR"
sudo mkdir -p "$INSTALL_DIR"
sudo chown "$USER":"$USER" "$INSTALL_DIR"

# Step 3. Clone or update repository
if [ -d "$INSTALL_DIR/.git" ]; then
    echo "[3] Repository already exists at $INSTALL_DIR."
    echo "[3a] Pulling latest changes..."
    git -C "$INSTALL_DIR" pull
else
    echo "[3] Cloning repository into $INSTALL_DIR..."
    git clone "$REPO_URL" "$INSTALL_DIR"
fi
cd "$INSTALL_DIR"

# Step 4. Remove and recreate virtual environment
echo "[4] Resetting virtual environment..."
rm -rf "$VENV_DIR"
python3 -m venv "$VENV_DIR"

# Step 5. Install Python dependencies into virtual environment
echo "[5] Installing Python packages (flask, paramiko)..."
"$VENV_DIR/bin/pip" install --no-cache-dir flask paramiko

# Step 6. Ensure nodes.json exists
echo "[6] Ensuring nodes.json exists..."
NODES_FILE="$INSTALL_DIR/nodes.json"
if [ -f "$NODES_FILE" ]; then
    echo "[6a] Backing up existing nodes.json..."
    cp "$NODES_FILE" "$NODES_FILE.bak"
    echo "[!] nodes.json already exists. Skipping creation."
else
    echo "[6] Creating empty nodes.json..."
    echo "[]" > "$NODES_FILE"
    echo "[+] Created nodes.json"
fi

# Step 7. Install systemd service
echo "[7] Installing systemd service..."
SERVICE_FILE="$INSTALL_DIR/systemd/system/servicemonitor.service"
if [ -f "$SERVICE_FILE" ]; then
    sudo cp "$SERVICE_FILE" "$SYSTEMD_DIR/"
    sudo systemctl daemon-reexec
    sudo systemctl daemon-reload
else
    echo "[ERROR] Service file not found at $SERVICE_FILE"
    exit 1
fi

# Step 8. Enable or restart service
if systemctl is-active --quiet servicemonitor.service; then
    echo "[8] Restarting servicemonitor.service..."
    sudo systemctl restart servicemonitor.service
else
    echo "[8] Enabling and starting servicemonitor.service..."
    sudo systemctl enable servicemonitor.service
    sudo systemctl start servicemonitor.service
fi

# Step 9. Preload cache to verify setup
echo "[9] Running prefetch_services.py once to verify..."
"$VENV_DIR/bin/python" "$INSTALL_DIR/prefetch_services.py"

# Step 10. Done
if command -v ip &> /dev/null; then
    LOCAL_IP=$(ip route get 1.1.1.1 | awk '{print $7; exit}')
elif command -v ifconfig &> /dev/null; then
    LOCAL_IP=$(ifconfig | awk '/inet / && $2 != "127.0.0.1" {print $2; exit}')
else
    LOCAL_IP="<unknown>"
fi
echo "✅ Installation complete."
echo "👉 Visit your dashboard at http://$LOCAL_IP:8484"
