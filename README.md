What netlab is
--------------
netlab is a single-host network attack/defense lab using Linux network namespaces. It runs four reproducible scenarios for learning, demonstration, and detection-rule testing.

What netlab isn't
-----------------
netlab is not a CTF platform, not a malware sandbox, and not a multi-host network simulator. It runs single-host scripted scenarios in isolated namespaces and exits.

Quick start
-----------
Run these commands from a freshly-cloned repository (pop/ubuntu 24.04):

```bash
git clone <repo-url> netlab && cd netlab
sudo ./lab/install-deps.sh
python3 -m venv .venv
.venv/bin/pip install --upgrade pip setuptools wheel
.venv/bin/pip install -e .
sudo .venv/bin/netlab list
sudo .venv/bin/netlab run arp_spoof
sudo .venv/bin/netlab clean
```

Scenarios
---------
- `arp_spoof` — ARP cache poisoning from `ns-atk` against `ns-srv`. See `attacks/01-arp-spoof/README.md`.
- `mitm` — MITM interception using bidirectional ARP poisoning and `attacks/02-mitm/intercept.py`.
- `dns_poison` — DNS response spoofing via MITM position. See `attacks/03-dns-poison/README.md`.
- `syn_flood` — Bounded SYN flood generator from `ns-atk` to `ns-srv`.

How netlab works
----------------
`lab/setup.sh` creates four network namespaces (`ns-atk`, `ns-def`, `ns-srv`, `ns-dns`) and a bridge `br-lab`. Scenarios are Python wrappers in `netlab/scenarios/` that invoke the existing attack scripts inside the `ns-atk` namespace. Events are emitted as JSON to a configurable output (`stdout`, `file`, or `http_post`) following `CONTRACT.md`.

Integration
-----------
netlab runs standalone and emits codex-contract events that external consumers can ingest. See `CONTRACT.md` for the event schema and `netlab --help` for runtime options.

Building / installing
---------------------
System deps are installed with `sudo ./lab/install-deps.sh`.
Install the Python package in editable mode:

```bash
.venv/bin/pip install -e .
```

Troubleshooting
---------------
If something leaves the host in a bad state, run:

```bash
sudo .venv/bin/netlab clean
```

If your system's `venv` module does create a `pip` executable, you can use that form instead; the `python -m pip` variant is the portable fallback.

See `docs/TESTING-GUIDE.md` for further troubleshooting steps.

License
-------
MIT
