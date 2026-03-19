# Netlab

Isolated network attack-and-defense lab using Linux namespaces.

## Quick start
```bash
sudo ./lab/setup.sh
sudo ./lab/status.sh
```

## Stop lab
```bash
sudo ./lab/teardown.sh
```

## Structure
- `lab/`: namespace topology + services
- `attacks/`: four attack exercises
- `defenses/`: mitigation and detection modules
- `captures/`: PCAP output
- `writeups/`: evidence-based exercise reports

## Sentinel integration
Netlab defense scripts default to:
- `/home/reddy/codex-workspace/sentinel`

Override when needed:
```bash
export SENTINEL_PATH=/custom/path/to/sentinel
```
