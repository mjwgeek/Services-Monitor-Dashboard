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
    if ! command -v python3 &> /dev/null; then
        echo "[ERROR] Failed to install Python 3. Please install it manually and run this script again."
        exit 1
    fi
    echo "[+] Python 3 installed successfully."
else
    echo "[+] Python 3 is already installed."
fi

# Step 2. Create installation directory
echo "[2] Creating directory: $INSTALL_DIR"
sudo mkdir -p "$INSTALL_DIR"
sudo chown "$USER":"$USER" "$INSTALL_DIR"

# Step 3. Clone or re-clone repository
if [ -d "$INSTALL_DIR/.git" ]; then
    echo "[!] Repository already cloned to $INSTALL_DIR."
    read -p "[3] Do you want to re-clone the repository? (y/N) " -r
    if [[ "$REPLY" =~ ^[Yy]$ ]]; then
        echo "[3a] Removing existing repository..."
        sudo rm -rf "$INSTALL_DIR"
        echo "[3b] Cloning from $REPO_URL..."
        git clone "$REPO_URL" "$INSTALL_DIR"
    else
        echo "[3c] Skipping clone."
    fi
else
    echo "[3] Cloning from $REPO_URL..."
    git clone "$REPO_URL" "$INSTALL_DIR"
fi
cd "$INSTALL_DIR"

# Step 4. Create virtual environment
echo "[4] Creating virtual environment..."
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

# Step 5. Install Python dependencies into virtual environment
echo "[5] Installing Python packages (flask, paramiko)..."
"$VENV_DIR/bin/pip" install --no-cache-dir flask paramiko

# Step 6. Ensure nodes.json exists
echo "[6] Ensuring nodes.json exists..."
NODES_FILE="$INSTALL_DIR/nodes.json"
if [ ! -f "$NODES_FILE" ]; then
    echo "[]" > "$NODES_FILE"
    echo "[+] Created empty nodes.json"
else
    echo "[!] nodes.json already exists. Skipping."
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

# Step 8. Enable and start service
echo "[8] Enabling and starting servicemonitor.service..."
sudo systemctl enable servicemonitor.service
sudo systemctl restart servicemonitor.service

# Step 9. Preload cache to verify setup
echo "[9] Running prefetch_services.py once to verify..."
"$VENV_DIR/bin/python" "$INSTALL_DIR/prefetch_services.py"

# Step 10. Done
LOCAL_IP=$(ip route get 1.1.1.1 | awk '{print $7; exit}')
echo "👉 Visit your dashboard at http://$LOCAL_IP:8484"

