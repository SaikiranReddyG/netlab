# Netlab

Isolated network attack-and-defense lab using Linux namespaces.

## Install dependencies
```bash
sudo ./lab/install-deps.sh
```

This installer supports both `apt-get` (Debian/Ubuntu) and `pacman` (Arch Linux).

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
- `../sentinel`

Override when needed:
```bash
export SENTINEL_PATH=/custom/path/to/sentinel
```
