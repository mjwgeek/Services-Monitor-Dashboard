import eventlet
eventlet.monkey_patch()
from flask import Flask, request, jsonify, send_file, redirect, flash
from flask_socketio import SocketIO, emit
import subprocess
import paramiko
import os
import json
import threading
from pathlib import Path
from time import time


app = Flask(__name__)
app.secret_key = "supersecret"
socketio = SocketIO(app)

BASE_DIR = "/home/servicemonitor"
NODES_FILE = os.path.join(BASE_DIR, "nodes.json")
PREFETCH_SCRIPT = os.path.join(BASE_DIR, "prefetch_services.py")
VENV_BIN = os.path.join(os.environ.get("VIRTUAL_ENV", "/home/servicemonitor/venv"), "bin", "python3")

log_processes = {}

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

def parse_lsof(proto, lines):
    seen = set()
    entries = []
    for line in lines[1:]:
        parts = line.split()
        if len(parts) < 9:
            continue
        process = parts[0]
        pid = parts[1]
        user = parts[2]
        port_part = parts[-2]
        if ':' not in port_part:
            continue
        port = port_part.split(":")[-1]
        key = (proto, port, process)
        if key in seen:
            continue
        seen.add(key)
        entries.append({
            "protocol": proto,
            "port": port,
            "process": process,
            "pid": pid,
            "user": user
        })
    return entries

def get_local_services():
    out = subprocess.check_output([
        "systemctl", "list-units", "--type=service", "--all", "--no-pager", "--no-legend"
    ], universal_newlines=True)
    return parse_systemctl_output(out)

def get_local_ports():
    tcp = subprocess.run(["lsof", "-nP", "-iTCP", "-sTCP:LISTEN"], stdout=subprocess.PIPE, text=True).stdout.splitlines()
    udp = subprocess.run(["lsof", "-nP", "-iUDP"], stdout=subprocess.PIPE, text=True).stdout.splitlines()
    return parse_lsof("TCP", tcp) + parse_lsof("UDP", udp)

def get_remote_services_and_ports(node):
    ssh = ssh_connect(node)
    combined = {"services": [], "ports": []}
    try:
        stdin, stdout, stderr = ssh.exec_command("systemctl list-units --type=service --all --no-pager --no-legend")
        combined["services"] = parse_systemctl_output(stdout.read().decode())
    except Exception:
        combined["services"] = []
    try:
        seen = set()
        ports = []
        for proto in ["TCP", "UDP"]:
            cmd = f"lsof -nP -i{proto}"
            if proto == "TCP":
                cmd += " -sTCP:LISTEN"
            stdin, stdout, stderr = ssh.exec_command(cmd)
            lines = stdout.read().decode().splitlines()
            ports += parse_lsof(proto, lines)
        combined["ports"] = ports
    except Exception:
        combined["ports"] = []
    ssh.close()
    return combined

@app.route('/')
def index():
    return send_file(os.path.join(BASE_DIR, 'templates', 'index.html'))

@app.route('/api/unified')
def api_unified():
    try:
        local_services = get_local_services()
        local_ports = get_local_ports()
    except Exception:
        local_services, local_ports = [], []

    local_node = {
        'node': 'LOCAL',
        'host': '127.0.0.1',
        'reachable': True,
        'services': local_services,
        'ports': local_ports
    }

    nodes = load_nodes()
    remote_data = []
    for node in nodes:
        try:
            combined = get_remote_services_and_ports(node)
            remote_data.append({
                "node": node["name"],
                "host": node["host"],
                "reachable": True,
                "services": combined["services"],
                "ports": combined["ports"]
            })
        except Exception:
            remote_data.append({
                "node": node["name"],
                "host": node["host"],
                "reachable": False,
                "services": [],
                "ports": []
            })

    return jsonify({
        "timestamp": int(time()),
        "data": [local_node] + remote_data
    })

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

@socketio.on("start_logs")
def start_logs(data):
    service = data.get("service")
    host = data.get("host")
    sid = request.sid

    if not service or not host:
        emit("log_line", {"line": "❌ Missing host or service"})
        return

    def stream_local():
        try:
            proc = subprocess.Popen(
                ["journalctl", "-u", service, "-f", "--no-pager"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
            )
            log_processes[sid] = proc
            for line in proc.stdout:
                socketio.emit("log_line", {"line": line.strip()}, to=sid)
        except Exception as e:
            socketio.emit("log_line", {"line": f"❌ Local log error: {e}"}, to=sid)

    def stream_remote(node):
        try:
            ssh = ssh_connect(node)
            channel = ssh.get_transport().open_session()
            channel.settimeout(10)
            channel.exec_command(f"journalctl -u {service} -f --no-pager")
            log_processes[sid] = channel

            socketio.emit("log_line", {"line": f"🔌 Connected to {node['name']} ({node['host']})"}, to=sid)

            while True:
                if channel.recv_ready():
                    chunk = channel.recv(4096).decode(errors="ignore")
                    lines = chunk.splitlines()
                    for line in lines:
                        socketio.emit("log_line", {"line": line}, to=sid)

                elif channel.exit_status_ready():
                    break

                eventlet.sleep(1)

            channel.close()
            ssh.close()

        except Exception as e:
            socketio.emit("log_line", {"line": f"❌ SSH error: {e}"}, to=sid)

    if host == "LOCAL":
        eventlet.spawn(stream_local)
    else:
        node = next((n for n in load_nodes() if n["name"] == host), None)
        if not node:
            emit("log_line", {"line": f"❌ Unknown node '{host}'"})
            return
        eventlet.spawn(lambda: stream_remote(node))

@socketio.on("disconnect")
def disconnect(sid):
    print(f"[SocketIO] Client disconnected: {sid}")
    proc = log_processes.pop(sid, None)
    if proc:
        try:
            if hasattr(proc, "terminate"):
                proc.terminate()
            elif hasattr(proc, "close"):
                proc.close()
        except Exception as e:
            print(f"[WARN] Failed to clean up logs for {sid}: {e}")

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=8484)
