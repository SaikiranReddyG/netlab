# Exercise 02: MITM

## Setup
- Confirm forwarding and ARP poisoning preconditions.

## Attack Steps
1. Start two-way ARP spoof.
2. Run interceptor script.
3. Generate HTTP traffic from victim.

## Evidence
- Capture: `captures/02-mitm.pcap`
- HTTP lines observed: _add here_

## Defense Applied
- nftables policy (`defenses/02-firewall/firewall.nft`)

## Result After Defense
- _document what was blocked and what remained allowed_
