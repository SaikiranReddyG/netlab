# Exercise 03: DNS Poison

## Setup
- DNS service active in `ns-dns` with `target.lab -> 10.0.0.10`

## Attack Steps
1. Run `poison.py` in `ns-atk`.
2. Trigger DNS lookup from target namespace.

## Evidence
- Capture: `captures/03-dns-poison.pcap`
- Spoofed answer details: _add here_

## Defense Applied
- IDS rule checks (`defenses/03-ids/sentinel-rules.yaml`)
- Firewall hardening if used

## Result After Defense
- _document behavior after controls_
