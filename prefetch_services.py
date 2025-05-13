#!/home/servicemonitor/venv/bin/python3
import json
import os
from app import load_nodes, get_local_services, get_remote_services

CACHE_FILE = "/home/servicemonitor/cache.json"

def update_cache():
    results = []

    # Add LOCAL node
    results.append({
        'node': 'LOCAL',
        'host': '127.0.0.1',
        'reachable': True,
        'services': get_local_services()
    })

    # Loop over remote nodes
    for node in load_nodes():
        try:
            services = get_remote_services(node)
            reachable = True
        except Exception as e:
            services = [{
                'name': f'[ERROR: {e}]',
                'load': 'n/a',
                'active': 'failed',
                'sub': 'n/a'
            }]
            reachable = False

        results.append({
            'node': node['name'],
            'host': node['host'],
            'reachable': reachable,
            'services': services
        })

    with open(CACHE_FILE, 'w') as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    update_cache()
