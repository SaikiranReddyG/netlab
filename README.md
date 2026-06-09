What netlab is
--------------
netlab is a single-host network attack/defense lab using Linux network namespaces. It runs reproducible attack and defense scenarios for learning, demonstration, and detection-rule testing.

What netlab isn't
-----------------
netlab is not a CTF platform, not a malware sandbox, and not a multi-host network simulator. It runs single-host scripted scenarios in isolated namespaces and exits.

Quick start
-----------
Run these commands from a freshly-cloned repository (Pop/Ubuntu 24.04):

```bash
git clone <repo-url> netlab && cd netlab
sudo ./lab/install-deps.sh
python3 -m venv .venv
.venv/bin/pip install --upgrade pip setuptools wheel
.venv/bin/pip install -e .
sudo .venv/bin/netlab run arp_spoof
```

Scenarios
---------
Attack scenarios:

- `arp_spoof`   — ARP cache poisoning from `ns-atk` against `ns-srv`
- `mitm`        — MITM interception using bidirectional ARP poisoning
- `dns_poison`  — DNS response spoofing via MITM position
- `syn_flood`   — Bounded SYN flood from `ns-atk` to `ns-srv`

Defense scenarios:

- `arp_defense` — Static ARP locking + Scapy ARP spoof detector (mitigates: arp_spoof, mitm, dns_poison)
- `firewall`    — nftables ruleset with SYN rate limiting and anti-spoof rules (mitigates: syn_flood, arp_spoof)
- `hardening`   — Kernel hardening via sysctl: rp_filter, arp_ignore, tcp_syncookies (mitigates: arp_spoof, mitm, syn_flood)
- `ids`         — Passive Scapy IDS on br-lab bridge, detection only, no locking (mitigates: arp_spoof, mitm, dns_poison)

Run commands
------------
List what's available:

```bash
.venv/bin/netlab list        # attack scenarios
.venv/bin/netlab defenses    # defense scenarios
```

Run a single attack scenario:

```bash
sudo .venv/bin/netlab run arp_spoof
sudo .venv/bin/netlab run syn_flood --params count=500
```

Apply a defense standalone (runs until Ctrl+C):

```bash
sudo .venv/bin/netlab defend arp_defense
sudo .venv/bin/netlab defend firewall
```

Run a paired attack + defense (pre-apply mode — defense set up first, then attack):

```bash
sudo .venv/bin/netlab pair arp_spoof arp_defense
sudo .venv/bin/netlab pair syn_flood firewall
```

Run a paired attack + defense in concurrent mode (both start simultaneously):

```bash
sudo .venv/bin/netlab pair arp_spoof ids --mode concurrent
```

Preview a run without touching the network:

```bash
sudo .venv/bin/netlab run arp_spoof --dry-run
```

TUI
---
The live TUI shows a split view — attack events on the left, defense events on the right — updated in real time as any run progresses.

Open two terminals:

Terminal 1:
```bash
.venv/bin/netlab tui
```

Terminal 2 (run any attack, defense, or pair):
```bash
sudo .venv/bin/netlab pair arp_spoof arp_defense --output stdout
```

TUI keyboard shortcuts:

| Key | Action |
|-----|--------|
| `Q` | Quit |
| `R` | Refresh |
| `Tab` | Switch focus between ATTACK / DEFENSE panels |
| `C` | Clear both logs |

Regression testing
------------------
Run the built-in test suite to verify all scenario steps and defense alerts fire correctly:

```bash
sudo .venv/bin/netlab test
```

Filter to a single scenario:

```bash
sudo .venv/bin/netlab test --filter arp_spoof
```

If Suricata is installed, also validate the pre-recorded pcap captures against the custom rule set:

```bash
sudo .venv/bin/netlab test --with-suricata
```

Exit codes: `0` all passed, `1` one or more assertions failed.

Event output
------------
All commands emit structured JSON events. Output destination is configurable:

```bash
# stdout (default)
sudo .venv/bin/netlab run arp_spoof --output stdout

# append to a file
sudo .venv/bin/netlab run arp_spoof --output file --output-file events.jsonl

# POST to an HTTP endpoint
sudo .venv/bin/netlab run arp_spoof --output http_post --output-url http://localhost:8765/events

# batch HTTP posts
sudo .venv/bin/netlab run arp_spoof --output http_post --output-url http://... --batch-size 10
```

Events also tee automatically to `.netlab-run/events.jsonl` — this is what the TUI reads.

See `CONTRACT.md` for the full event schema, event types, and payload conventions.

How netlab works
----------------
`lab/setup.sh` creates four network namespaces (`ns-atk`, `ns-def`, `ns-srv`, `ns-dns`) connected via a bridge `br-lab`. Attack scenarios run Python wrappers in `netlab/scenarios/` that invoke scripts in `attacks/` inside `ns-atk`. Defense scenarios run wrappers in `netlab/defenses/` that apply scripts from `defenses/`. All events are emitted as JSON following `CONTRACT.md`.

Namespace layout:

```
ns-atk  10.0.0.2    — attacker
ns-def  10.0.0.3    — defender / monitor
ns-srv  10.0.0.10   — target server (HTTP + DNS)
ns-dns  10.0.0.53   — DNS server
        br-lab      — bridge connecting all four
```

Status and cleanup
------------------
Check lab state:

```bash
sudo .venv/bin/netlab status
sudo .venv/bin/netlab status --json
```

Clean up any leftover state:

```bash
sudo .venv/bin/netlab clean
```

Building / installing
---------------------
System dependencies:

```bash
sudo ./lab/install-deps.sh
```

Install the Python package in editable mode:

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/pip install -e ".[dev]"   # includes pytest
```

Run unit tests:

```bash
.venv/bin/pytest tests/
```

Troubleshooting
---------------
If something leaves the host in a bad state:

```bash
sudo .venv/bin/netlab clean
```

See `docs/TESTING-GUIDE.md` for further troubleshooting steps.

License
-------
MIT
