# Exercise 04: SYN Flood

## Setup
- Target HTTP service running on `10.0.0.10:80`
- Packet flood generated from attacker namespace using `attacks/04-syn-flood/flood.sh`.

## Attack Steps
1. Run bounded flood script.
2. Observe service responsiveness and packet rate.
3. Capture SYN packets on target namespace interface for evidence.

## Evidence
- Capture: `captures/04-syn-flood.pcap`
- Flood run statistics observed from tool output:
	- `3000 packets transmitted, 3000 packets received, 0% packet loss`
	- `round-trip min/avg/max = 0.0/0.5/1.0 ms`
- Target-facing packet activity captured during flood run.

## Defense Applied
- nftables SYN rate limiting
- kernel hardening (`tcp_syncookies`)

Verified controls after applying defenses:
- `net.ipv4.tcp_syncookies = 1`
- Active nftables policy on `ns-srv` includes:
	- `policy drop` on input/forward chains
	- `tcp flags syn limit rate 25/second burst 50 packets accept`
	- explicit service allow-list and invalid-state drops

## Result After Defense
- Defensive controls were successfully enabled and verified in-kernel/ruleset output.
- Final quantitative post-defense throughput/availability comparison remains optional for a follow-up stress run.
