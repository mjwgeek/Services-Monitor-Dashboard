import json
import os
import subprocess

NODES_FILE = 'nodes.json'
SSH_KEY_PATH = os.path.expanduser("~/.ssh/id_rsa")

def ensure_ssh_key():
    if not os.path.exists(SSH_KEY_PATH):
        print("[+] SSH key not found, generating one...")
        subprocess.run(['ssh-keygen', '-t', 'rsa', '-b', '4096', '-N', '', '-f', SSH_KEY_PATH])
    else:
        print("[✓] SSH key already exists.")

def install_key(node):
    print(f"\n[*] Installing key on {node['name']} ({node['host']}:{node['port']})...")

    cmd = [
        "sshpass", "-p", node["password"],
        "ssh", "-o", "StrictHostKeyChecking=no",
        "-p", str(node["port"]),
        f"{node['user']}@{node['host']}",
        f"mkdir -p ~/.ssh && chmod 700 ~/.ssh && echo '{open(SSH_KEY_PATH + '.pub').read().strip()}' >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
    ]

    try:
        subprocess.run(cmd, check=True)
        print(f"[✓] Key installed on {node['name']}")
        node["use_key"] = True  # Mark this node as using key-based login now
    except subprocess.CalledProcessError as e:
        print(f"[✗] Failed to install key on {node['name']}: {e}")

def main():
    if not os.path.exists(NODES_FILE):
        print(f"[-] Cannot find {NODES_FILE}")
        return

    ensure_ssh_key()

    with open(NODES_FILE, 'r') as f:
        nodes = json.load(f)

    for node in nodes:
        install_key(node)

    with open(NODES_FILE, 'w') as f:
        json.dump(nodes, f, indent=2)

    print("\n✅ All done! Now you can use key-based login for these systems.")

if __name__ == "__main__":
    main()
