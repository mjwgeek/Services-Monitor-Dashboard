from flask import Flask, request, jsonify, send_file, redirect, flash
import subprocess
import paramiko
import os
import json
import threading
from pathlib import Path
from time import time

app = Flask(__name__)
app.secret_key = "supersecret"

BASE_DIR = "/home/servicemonitor"
NODES_FILE = os.path.join(BASE_DIR, "nodes.json")
PREFETCH_SCRIPT = os.path.join(BASE_DIR, "prefetch_services.py")
VENV_BIN = os.path.join(os.environ.get("VIRTUAL_ENV", "/home/servicemonitor/venv"), "bin", "python3")

def load_nodes():
    if not os.path.exists(NODES_FILE):
        return []
    with open(NODES_FILE) as f:
        return json.load(f)

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
    for line in output.strip().split("\n"):
        parts = line.split()
        if len(parts) >= 4:
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

def parse_lsof(proto):
    cmd = ["lsof", "-nP", f"-i{proto}"]
    if proto == "TCP":
        cmd += ["-sTCP:LISTEN"]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    lines = result.stdout.strip().splitlines()
    entries = []
    for line in lines[1:]:
        parts = line.split()
        if len(parts) < 9:
            continue
        entries.append({
            "protocol": proto,
            "port": parts[-2].split(":")[-1],
            "process": parts[0],
            "pid": parts[1],
            "user": parts[2]
        })
    return entries

def get_local_ports():
    return parse_lsof("TCP") + parse_lsof("UDP")

def get_remote_ports(node):
    ssh = ssh_connect(node)
    results = []
    for proto in ["TCP", "UDP"]:
        cmd = f"lsof -nP -i{proto}"
        if proto == "TCP":
            cmd += " -sTCP:LISTEN"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        lines = stdout.read().decode().splitlines()
        for line in lines[1:]:
            parts = line.split()
            if len(parts) < 9:
                continue
            results.append({
                "protocol": proto,
                "port": parts[-2].split(":")[-1],
                "process": parts[0],
                "pid": parts[1],
                "user": parts[2]
            })
    ssh.close()
    return results

@app.route('/')
def index():
    return send_file(os.path.join(BASE_DIR, 'templates', 'index.html'))

@app.route('/api/services')
def api_services():
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

    nodes = load_nodes()
    remote_data = []
    for node in nodes:
        try:
            services = get_remote_services(node)
            remote_data.append({
                "node": node["name"],
                "host": node["host"],
                "reachable": True,
                "services": services
            })
        except Exception:
            remote_data.append({
                "node": node["name"],
                "host": node["host"],
                "reachable": False,
                "services": []
            })

    return jsonify({ "timestamp": int(time()), "data": [local_node] + remote_data })

@app.route('/api/ports')
def api_ports():
    try:
        local_ports = get_local_ports()
    except Exception:
        local_ports = []

    local_node = {
        'node': 'LOCAL',
        'host': '127.0.0.1',
        'reachable': True,
        'ports': local_ports
    }

    nodes = load_nodes()
    remote_data = []
    for node in nodes:
        try:
            ports = get_remote_ports(node)
            remote_data.append({
                "node": node["name"],
                "host": node["host"],
                "reachable": True,
                "ports": ports
            })
        except Exception:
            remote_data.append({
                "node": node["name"],
                "host": node["host"],
                "reachable": False,
                "ports": []
            })

    return jsonify([local_node] + remote_data)

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
    with open(NODES_FILE, "w") as f:
        json.dump(nodes, f, indent=2)
    threading.Thread(target=lambda: subprocess.run([VENV_BIN, PREFETCH_SCRIPT], cwd=BASE_DIR), daemon=True).start()
    return jsonify({"success": True, "message": "Machine added successfully."})

@app.route('/force-refresh', methods=["POST"])
def force_refresh():
    try:
        subprocess.run([VENV_BIN, PREFETCH_SCRIPT], check=True)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

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

@app.route('/logs', methods=["POST"])
def logs():
    try:
        data = request.get_json()
        host = data.get("host")
        service = data.get("service")
        follow = data.get("follow", False)
        nodes = load_nodes()
        if host == "LOCAL":
            cmd = ["journalctl", "-u", service, "--no-pager", "-n", "10" if follow else "50"]
            output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=2, universal_newlines=True)
        else:
            node = next((n for n in nodes if n["name"] == host), None)
            if not node:
                return jsonify({"success": False, "message": f"Node '{host}' not found"})
            ssh = ssh_connect(node)
            cmd = f"journalctl -u {service} --no-pager -n {'10' if follow else '50'}"
   
            stdin, stdout, stderr = ssh.exec_command(cmd)
            output = stdout.read().decode() or stderr.read().decode()
            ssh.close()
        return jsonify({"success": True, "logs": output})
    except subprocess.TimeoutExpired:
        return jsonify({"success": True, "logs": ""})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8484, threaded=True)
