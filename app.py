from flask import Flask, send_file, request, redirect, jsonify, flash
import subprocess
import paramiko
import os
import json
import threading
from pathlib import Path

# Initialize Flask without blocking template loading
app = Flask(__name__)
app.secret_key = "supersecret"

# Base paths
BASE_DIR = "/home/servicemonitor"
CACHE_FILE = os.path.join(BASE_DIR, "cache.json")
NODES_FILE = os.path.join(BASE_DIR, "nodes.json")
PREFETCH_SCRIPT = os.path.join(BASE_DIR, "prefetch_services.py")
# Add VENV_BIN - this should be defined in your environment or you can hardcode it, but hardcoding is not recommended.
VENV_BIN = os.path.join(os.environ.get("VIRTUAL_ENV", "/home/servicemonitor/venv"), "bin", "python3")

# Node management
def load_nodes():
    if not os.path.exists(NODES_FILE):
        return []
    with open(NODES_FILE) as f:
        return json.load(f)

def save_nodes(nodes):
    with open(NODES_FILE, "w") as f:
        json.dump(nodes, f, indent=2)

# SSH helper
def ssh_connect(node):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    key_path = node.get("key_path", "/root/.ssh/id_rsa")
    if node.get("use_key", True):
        pkey = paramiko.RSAKey.from_private_key_file(key_path)
        ssh.connect(node["host"], port=node["port"], username=node["user"], pkey=pkey, timeout=5)
    else:
        ssh.connect(node["host"], port=node["port"], username=node.get("password"), timeout=5)
    return ssh

# Parse systemctl output
def parse_systemctl_output(output):
    services = []
    for line in output.strip().split("\n"):
        parts = line.split()
        if len(parts) >= 5:
            name, load, active, sub = parts[:4]
            if load == "not-found":
                continue
            services.append({'name': name, 'load': load, 'active': active, 'sub': sub})
    return services

# Local and remote services
def get_local_services():
    out = subprocess.check_output([
        "systemctl", "list-units", "--type=service", "--all", "--no-pager", "--no-legend"
    ], universal_newlines=True)
    return parse_systemctl_output(out)

def get_remote_services(node):
    ssh = ssh_connect(node)
    stdin, stdout, stderr = ssh.exec_command(
        "systemctl list-units --type=service --all --no-pager --no-legend"
    )
    output = stdout.read().decode()
    ssh.close()
    return parse_systemctl_output(output)

# Serve static index.html immediately
@app.route('/')
def index():
    # Serve the static index.html immediately using send_file
    index_path = os.path.join(BASE_DIR, 'templates', 'index.html')
    return send_file(index_path)

@app.route('/api/services')
def api_services():
    # Always include local services immediately
    try:
        local_services = get_local_services()
    except Exception:
        local_services = []
    local_node = {
        'node': 'LOCAL',
        'host': '127.0.0.1',
        'reachable': True,
        'services': local_services
    }
    # Load remote nodes from cache (or trigger prefetch)
    remote_data = []
    if not os.path.exists(CACHE_FILE):
        threading.Thread(
            target=lambda: subprocess.run([
                VENV_BIN, PREFETCH_SCRIPT  # Use VENV_BIN
            ], cwd=BASE_DIR), daemon=True
        ).start()
    else:
        with open(CACHE_FILE) as f:
            remote_data = json.load(f)
    timestamp = os.path.getmtime(CACHE_FILE) if os.path.exists(CACHE_FILE) else None
    # Combine local and remote (avoid duplicating LOCAL)
    combined = [local_node] + [n for n in remote_data if n.get('node') != 'LOCAL']
    return jsonify({"timestamp": timestamp, "data": combined})

@app.route('/action', methods=["POST"])
def action():
    host = request.form['host']
    service = request.form['service']
    act = request.form['action']
    nodes = load_nodes()
    if host == 'LOCAL':
        subprocess.run(['systemctl', act, service], check=False)
    else:
        node = next((n for n in nodes if n['name'] == host), None)
        if not node:
            flash(f"Host '{host}' not found.")
            return redirect('/')
        try:
            ssh = ssh_connect(node)
            ssh.exec_command(f"systemctl {act} {service}")
            ssh.close()
        except Exception as e:
            flash(f"SSH error: {e}")
            return redirect('/')
    flash(f"{act.capitalize()} sent to {service} on {host}")
    return redirect('/')

# Prefetch endpoint
@app.route('/api/prefetch', methods=["POST"])
def api_prefetch():
    try:
        subprocess.run([VENV_BIN, PREFETCH_SCRIPT], check=True) # Use VENV_BIN
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# Force refresh endpoint
@app.route('/force-refresh', methods=["POST"])
def force_refresh():
    try:
        subprocess.run([VENV_BIN, PREFETCH_SCRIPT], check=True) # Use VENV_BIN
        return jsonify({"success": True, "message": "Cache refreshed"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

# Node addition endpoint
@app.route('/add_node', methods=["POST"])
def add_node():
    data = request.get_json()
    name = data.get('name')
    host = data.get('host')
    port = int(data.get('port', 22))
    user = data.get('user')
    password = data.get('password')
    if not all([name, host, port, user]):
        return jsonify({"success": False, "message": "Missing fields"})
    key_file = f"/root/.ssh/id_rsa_{host.replace('.', '_')}"
    pub_file = key_file + '.pub'
    if not Path(key_file).exists():
        subprocess.run(["ssh-keygen", "-t", "rsa", "-b", "2048", "-f", key_file, "-N", ""], check=True)
    if password:
        try:
            pubkey = Path(pub_file).read_text().strip()
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(hostname=host, port=port, username=user, password=password, timeout=10)
            ssh.exec_command("mkdir -p ~/.ssh && chmod 700 ~/.ssh")
            ssh.exec_command(f'echo "{pubkey}" >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys')
            ssh.close()
        except Exception as e:
            return jsonify({"success": False, "message": f"Key copy failed: {e}"})
    node_entry = {"name": name, "host": host, "port": port, "user": user, "use_key": True, "key_path": key_file}
    nodes = load_nodes()
    nodes.append(node_entry)
    save_nodes(nodes)
    threading.Thread(target=lambda: subprocess.run([VENV_BIN, PREFETCH_SCRIPT], cwd=BASE_DIR), daemon=True).start() # Use VENV_BIN
    return jsonify({"success": True, "message": "Machine added successfully."})
    
@app.route('/logs', methods=["POST"])
def logs():
    try:
        data = request.get_json()
        host = data.get("host")
        service = data.get("service")
        follow = data.get("follow", False)
        nodes = load_nodes()

        if host == "LOCAL":
            # Use -n 50 for live, -n 100 for standard
            lines = "50" if follow else "100"
            cmd = ["journalctl", "-u", service, "--no-pager", "-n", lines]
            output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, universal_newlines=True)

        else:
            node = next((n for n in nodes if n["name"] == host), None)
            if not node:
                return jsonify({"success": False, "message": f"Node '{host}' not found"})

            ssh = ssh_connect(node)
            lines = "50" if follow else "100"
            cmd = f"journalctl -u {service} --no-pager -n {lines}"
            stdin, stdout, stderr = ssh.exec_command(cmd)
            output = stdout.read().decode() or stderr.read().decode()
            ssh.close()

        return jsonify({"success": True, "logs": output})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8484, threaded=True)
