#!/bin/bash
set -e

# Configuration variables
INSTALL_DIR="/home/servicemonitor"
REPO_URL="https://github.com/mjwgeek/Services-Monitor-Dashboard.git"
SYSTEMD_DIR="/etc/systemd/system"
VENV_DIR="$INSTALL_DIR/venv" # Define virtual environment directory

echo "🛠️ Starting Service Monitor installation..."

# 0. Check for Python 3 and install if missing
echo "[*] Checking for Python 3..."
if ! command -v python3 &> /dev/null; then
    echo "[!] Python 3 not found. Attempting to install..."
    sudo apt update
    sudo apt install -y python3 python3-pip python3-venv  # Install python3-venv
    if ! command -v python3 &> /dev/null; then
        echo "[ERROR] Failed to install Python 3. Please install it manually and run this script again."
        exit 1
    fi
    echo "[+] Python 3 installed successfully."
else
    echo "[+] Python 3 is already installed."
fi

# 1. Create installation directory
echo "[*] Creating directory: $INSTALL_DIR"
sudo mkdir -p "$INSTALL_DIR"
sudo chown "$USER":"$USER" "$INSTALL_DIR"

# 2. Clone or re-clone repository
if [ -d "$INSTALL_DIR/.git" ]; then
    echo "[!] Repository already cloned to $INSTALL_DIR."
    read -p "Do you want to re-clone the repository? (y/N) " -r
    if [[ "$REPLY" =~ ^[Yy]$ ]]; then
        echo "[*] Removing existing repository..."
        sudo rm -rf "$INSTALL_DIR"
        echo "[*] Cloning from $REPO_URL..."
        git clone "$REPO_URL" "$INSTALL_DIR"
    else
        echo "[!] Skipping clone."
    fi
else
    echo "[*] Cloning from $REPO_URL..."
    git clone "$REPO_URL" "$INSTALL_DIR"
fi
cd "$INSTALL_DIR"

# 3. Create and activate a virtual environment
echo "[*] Creating virtual environment..."
python3 -m venv "$VENV_DIR" # create
VENV_BIN="$VENV_DIR/bin" # Define the virtual environment's bin directory
source "$VENV_BIN/activate" # activate

# 4. Install Python dependencies into the virtual environment
echo "[*] Installing Python packages (flask, paramiko) into virtual environment..."
"$VENV_BIN/pip3" install flask paramiko # Use the virtual environment's pip3

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
# Modify the service file to use the virtual environment's python
sudo sed -i "s|ExecStart=/usr/bin/python3|ExecStart=$VENV_BIN/python3|" "$SYSTEMD_DIR/servicemonitor.service"
sudo systemctl daemon-reexec
sudo systemctl daemon-reload

# 7. Enable and start main dashboard
echo "[*] Enabling and starting servicemonitor.service..."
sudo systemctl enable servicemonitor.service
sudo systemctl restart servicemonitor.service

# 8. Done
echo "✅ Installation complete."
echo "👉 Visit your dashboard at http://<your_server_ip>:8484"
