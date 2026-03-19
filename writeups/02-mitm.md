# Exercise 02: MITM

## Setup
- Enabled forwarding in attacker namespace (`ns-atk`).
- Ran bidirectional ARP poisoning between victim (`ns-def`, `10.0.0.3`) and target (`ns-srv`, `10.0.0.10`).

## Attack Steps
1. Start two-way ARP spoof.
2. Start packet capture on attacker interface (`veth-atk`) for `tcp port 80`.
3. Generate HTTP traffic from victim with repeated curl requests.

## Evidence
- Capture: `captures/02-mitm.pcap`
- Capture size: `8.4K`.
- Observed plaintext request and response in attacker-side PCAP:
	- `HTTP: GET / HTTP/1.1`
	- `HTTP: HTTP/1.0 200 OK`
- Sample flow observed:
	- `10.0.0.3:42916 -> 10.0.0.10:80` (request)
	- `10.0.0.10:80 -> 10.0.0.3:42916` (response)
- Duplicate packets are expected in this bridged MITM setup and do not invalidate results.

## Defense Applied
- nftables policy (`defenses/02-firewall/firewall.nft`)

## Result After Defense
- Firewall and hardening controls were applied successfully in the server namespace and verified via active nftables ruleset and kernel `tcp_syncookies=1` output.
- Pre-defense MITM visibility was confirmed by captured plaintext HTTP request/response traffic in `captures/02-mitm.pcap`.
- A quantitative post-defense replay can be run as an optional follow-up to measure reduction in visible/forwarded attack traffic.
