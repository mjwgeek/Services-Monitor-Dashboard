from flask import Flask, render_template, request, redirect, jsonify, flash
import subprocess
import paramiko
import os
import json
import threading
from pathlib import Path

app = Flask(__name__)
app.secret_key = "supersecret"

BASE_DIR = "/home/mike/servicemonitor"
CACHE_FILE = f"{BASE_DIR}/cache.json"
NODES_FILE = f"{BASE_DIR}/nodes.json"
PREFETCH_SCRIPT = f"{BASE_DIR}/prefetch_services.py"

def load_nodes():
    with open(NODES_FILE) as f:
        return json.load(f)

def save_nodes(nodes):
    with open(NODES_FILE, "w") as f:
        json.dump(nodes, f, indent=2)

def ssh_connect(node):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    key_path = node.get("key_path", "/root/.ssh/id_rsa")
    if node.get("use_key", True):
        pkey = paramiko.RSAKey.from_private_key_file(key_path)
        ssh.connect(node["host"], port=node["port"], username=node["user"], pkey=pkey, timeout=5)
    else:
        ssh.connect(node["host"], port=node["port"], username=node["user"], password=node.get("password"), timeout=5)
    return ssh

def parse_systemctl_output(output):
    services = []
    for line in output.strip().split('\n'):
        parts = line.split()
        if len(parts) >= 5:
            name, load, active, sub = parts[:4]
            if load == "not-found":
                continue
            services.append({'name': name, 'load': load, 'active': active, 'sub': sub})
    return services

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

@app.route('/')
def index():
    # Serve the template right away, without waiting for any service lookups or cache reads
    return render_template('index.html')

@app.route('/api/services')
def api_services():
    # If cache missing, spawn background prefetch then return empty
    if not os.path.exists(CACHE_FILE):
        threading.Thread(
            target=lambda: subprocess.run(
                ["/usr/bin/python3", PREFETCH_SCRIPT], cwd=BASE_DIR
            ),
            daemon=True
        ).start()
        return jsonify({"timestamp": None, "data": []})
    with open(CACHE_FILE) as f:
        data = json.load(f)
    timestamp = os.path.getmtime(CACHE_FILE)
    return jsonify({"timestamp": timestamp, "data": data})

@app.route('/action', methods=["POST"])
def action():
    host = request.form["host"]
    service = request.form["service"]
    act = request.form["action"]
    nodes = load_nodes()

    if host == "LOCAL":
        subprocess.run(["systemctl", act, service], check=False)
    else:
        node = next((n for n in nodes if n["name"] == host), None)
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

@app.route('/api/prefetch', methods=["POST"])
def api_prefetch():
    try:
        subprocess.run(["/usr/bin/python3", PREFETCH_SCRIPT], check=True)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/force-refresh', methods=["POST"])
def force_refresh():
    try:
        subprocess.run(["/usr/bin/python3", PREFETCH_SCRIPT], check=True)
        return jsonify({"success": True, "message": "Cache refreshed"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/add_node', methods=["POST"])
def add_node():
    data = request.get_json()
    name = data.get("name")
    host = data.get("host")
    port = int(data.get("port", 22))
    user = data.get("user")
    password = data.get("password")
    if not all([name, host, port, user]):
        return jsonify({"success": False, "message": "Missing fields"})

    key_file = f"/root/.ssh/id_rsa_{host.replace('.', '_')}"
    pub_file = key_file + ".pub"
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

    # Trigger immediate prefetch asynchronously
    threading.Thread(target=lambda: subprocess.run(["/usr/bin/python3", PREFETCH_SCRIPT], cwd=BASE_DIR), daemon=True).start()
    return jsonify({"success": True, "message": "Machine added successfully."})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8484, threaded=True)
