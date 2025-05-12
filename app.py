from flask import Flask, render_template, request, redirect, jsonify, flash
import subprocess
import paramiko
import os
import json
import threading
from pathlib import Path

app = Flask(__name__)
app.secret_key = "supersecret"

CACHE_FILE = "/home/servicemonitor/cache.json"
NODES_FILE = "/home/servicemonitor/nodes.json"

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

def get_local_services():
    output = subprocess.check_output(["systemctl", "list-units", "--type=service", "--all", "--no-pager", "--no-legend"], universal_newlines=True)
    return parse_systemctl_output(output)

def get_remote_services(node):
    ssh = ssh_connect(node)
    stdin, stdout, stderr = ssh.exec_command("systemctl list-units --type=service --all --no-pager --no-legend")
    output = stdout.read().decode()
    ssh.close()
    return parse_systemctl_output(output)

def parse_systemctl_output(output):
    services = []
    for line in output.strip().split('\n'):
        parts = line.split()
        if len(parts) >= 5:
            name, load, active, sub = parts[:4]
            if load == "not-found":
                continue
            services.append({
                'name': name,
                'load': load,
                'active': active,
                'sub': sub
            })
    return services

@app.route('/')
def index():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE) as f:
            results = json.load(f)
    else:
        results = [{
            'node': 'LOCAL',
            'host': '127.0.0.1',
            'reachable': True,
            'services': get_local_services()
        }]
    return render_template('index.html', results=results)

@app.route('/api/services')
def api_services():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE) as f:
            data = json.load(f)
        timestamp = os.path.getmtime(CACHE_FILE)
        return jsonify({"timestamp": timestamp, "data": data})
    return jsonify({"timestamp": None, "data": []})

@app.route('/action', methods=["POST"])
def action():
    host = request.form["host"]
    service = request.form["service"]
    action = request.form["action"]
    nodes = load_nodes()

    if host == "LOCAL":
        cmd = ["systemctl", action, service]
        result = subprocess.run(cmd, capture_output=True)
    else:
        node = next((n for n in nodes if n["name"] == host), None)
        if not node:
            flash(f"Host '{host}' not found.")
            return redirect("/")
        try:
            ssh = ssh_connect(node)
            ssh.exec_command(f"systemctl {action} {service}")
            ssh.close()
        except Exception as e:
            flash(f"SSH error: {e}")
            return redirect("/")

    flash(f"{action.capitalize()} sent to {service} on {host}")
    return redirect("/")

@app.route('/force-refresh', methods=["POST"])
def force_refresh():
    try:
        subprocess.run(["/usr/bin/python3", "/home/servicemonitor/prefetch_services.py"], check=True)
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
    password = data.get("password", None)

    if not all([name, host, port, user]):
        return jsonify({"success": False, "message": "Missing fields"})

    key_file = f"/root/.ssh/id_rsa_{host.replace('.', '_')}"
    pub_file = f"{key_file}.pub"

    # Create key if not present
    if not Path(key_file).exists():
        subprocess.run(["ssh-keygen", "-t", "rsa", "-b", "2048", "-f", key_file, "-N", ""])

    if password:
        try:
            # Copy pubkey via password auth
            pubkey = Path(pub_file).read_text().strip()
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(hostname=host, port=port, username=user, password=password, timeout=10)

            ssh.exec_command("mkdir -p ~/.ssh && chmod 700 ~/.ssh")
            ssh.exec_command(f'echo "{pubkey}" >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys')
            ssh.close()
        except Exception as e:
            return jsonify({"success": False, "message": f"Key copy failed: {e}"})

    node_entry = {
        "name": name,
        "host": host,
        "port": port,
        "user": user,
        "use_key": True,
        "key_path": key_file
    }

    nodes = load_nodes()
    nodes.append(node_entry)
    save_nodes(nodes)

    def trigger_refresh():
        subprocess.run(["/usr/bin/python3", "/home/servicemonitor/prefetch_services.py"])

    threading.Thread(target=trigger_refresh).start()

    return jsonify({"success": True, "message": "Machine added successfully."})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8484)
