# Exercise 01: ARP Spoof

## Setup
- Lab started with `sudo ./lab/setup.sh`

## Attack Steps
1. Run ARP spoof from `ns-atk`.
2. Observe ARP neighbor entry in `ns-srv` for gateway.

## Evidence
- Capture: `captures/01-arp-spoof.pcap`
- Command output snippets: _add here_

## Defense Applied
- Static ARP (`defenses/01-arp-defense/static-arp.sh`)
- Detector (`defenses/01-arp-defense/detect.py`)

## Result After Defense
- _document final behavior and residual risk_
