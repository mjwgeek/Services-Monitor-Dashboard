#!/bin/bash
set -e

# Configuration variables
INSTALL_DIR="/home/servicemonitor"
REPO_URL="https://github.com/mjwgeek/Services-Monitor-Dashboard.git"
SYSTEMD_DIR="/etc/systemd/system"
VENV_DIR="$INSTALL_DIR/venv" # Define virtual environment directory
APP_DIR="$INSTALL_DIR" # Application directory is the same as install dir

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
source "$VENV_DIR/bin/activate" # activate

# 4. Install Python dependencies into the virtual environment
echo "[*] Installing Python packages (flask, paramiko) into virtual environment..."
"$VENV_BIN/pip3" install --no-cache-dir flask paramiko # Use the virtual environment's pip3 and disable cache

# 5. # Application directory is the same as install dir, so no need to create or copy
#echo "[*] Creating application directory: $APP_DIR"
#sudo mkdir -p "$APP_DIR"
#sudo chown "$USER":"$USER" "$APP_DIR"

# 6. # No need to copy files, they are already in the correct location
#echo "[*] Copying application files to $APP_DIR"
# Copy all files from the repo to the app dir, excluding the venv and the script itself
#find . -mindepth 1 -maxdepth 1 ! -name "venv" ! -name "install.sh" -exec cp -r {} "$APP_DIR" \;
#Remove venv from app dir.  The find command already excludes it, but this is here for safety.
rm -rf "$VENV_DIR"

# 7. Ensure nodes.json exists (empty list)
NODES_FILE="$APP_DIR/nodes.json" #check inside APP_DIR
if [ ! -f "$NODES_FILE" ]; then
    echo "[*] Creating empty nodes.json..."
    echo "[]" > "$NODES_FILE"
else
    echo "[!] nodes.json already exists. Skipping."
fi

# 8. Install systemd service files
echo "[*] Installing systemd services..."
if [ -f "systemd/system/servicemonitor.service" ]; then
    sudo cp systemd/system/servicemonitor.service "$SYSTEMD_DIR/"
    # Modify the service file to use the virtual environment's python and the correct application path
    sudo sed -i "s|ExecStart=/usr/bin/python3|ExecStart=$VENV_BIN/python3|" "$SYSTEMD_DIR/servicemonitor.service"
    #sudo sed -i "s|/home/servicemonitor|${APP_DIR}|" "$SYSTEMD_DIR/servicemonitor.service" #correct path in systemd - no longer needed
    sudo systemctl daemon-reexec
    sudo systemctl daemon-reload
else
    echo "[!] systemd service file not found in the cloned repository.  Please ensure it exists."
    exit 1
fi

# 9. Enable and start main dashboard
echo "[*] Enabling and starting servicemonitor.service..."
sudo systemctl enable servicemonitor.service
sudo systemctl restart servicemonitor.service

# 10. Done
echo "✅ Installation complete."
echo "👉 Visit your dashboard at http://<your_server_ip>:8484"
```
