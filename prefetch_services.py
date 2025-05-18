#!/home/servicemonitor/venv/bin/python3
import json
from app import load_nodes, get_local_services, get_local_ports, get_remote_services_and_ports
from time import time

CACHE_FILE = "/home/servicemonitor/cache.json"

def update_cache():
    results = []

    # Add LOCAL node
    results.append({
        'node': 'LOCAL',
        'host': '127.0.0.1',
        'reachable': True,
        'services': get_local_services(),
        'ports': get_local_ports()
    })

    # Loop over remote nodes
    for node in load_nodes():
        try:
            combined = get_remote_services_and_ports(node)
            services = combined.get("services", [])
            ports = combined.get("ports", [])
            reachable = True
        except Exception as e:
            services = [{
                'name': f'[ERROR: {e}]',
                'load': 'n/a',
                'active': 'failed',
                'sub': 'n/a'
            }]
            ports = []
            reachable = False

        results.append({
            'node': node['name'],
            'host': node['host'],
            'reachable': reachable,
            'services': services,
            'ports': ports
        })

    # Wrap in timestamped structure
    output = {
        "timestamp": int(time()),
        "data": results
    }

    with open(CACHE_FILE, 'w') as f:
        json.dump(output, f, indent=2)

if __name__ == "__main__":
    update_cache()
