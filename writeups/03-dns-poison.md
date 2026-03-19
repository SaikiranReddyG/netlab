# Exercise 03: DNS Poison

## Setup
- DNS service active in `ns-dns` with `target.lab -> 10.0.0.10`
- Attacker inserted in-path between victim (`10.0.0.3`) and DNS server (`10.0.0.53`) using bidirectional ARP poisoning.

## Attack Steps
1. Run `poison.py` in `ns-atk`.
2. Trigger repeated DNS lookups from victim namespace (`ns-def`) to `10.0.0.53`.
3. Capture UDP/53 traffic on attacker interface (`veth-atk`).

## Evidence
- Capture: `captures/03-dns-poison.pcap`
- Capture size: `9.2K` (non-empty DNS traffic observed).
- Victim queries captured:
	- `10.0.0.3.x > 10.0.0.53.53: A? target.lab`
- Legitimate DNS responses captured:
	- `10.0.0.53.53 > 10.0.0.3.x: A 10.0.0.10`
- Spoofed response captured from attacker-influenced flow:
	- `10.0.0.53.53 > 10.0.0.3.51536: ... A 10.0.0.2`
- `nslookup` still printing `10.0.0.10` indicates race/timing dominance by the legit response in that run, but PCAP confirms successful spoof injection.

## Defense Applied
- IDS rule checks (`defenses/03-ids/sentinel-rules.yaml`)
- Firewall hardening if used

## Result After Defense
- DNS spoof injection was confirmed at packet level (`A 10.0.0.2`) while legitimate resolver replies (`A 10.0.0.10`) still won most client races in this run.
- IDS and firewall defenses are in place for replay validation; practical mitigation focus is reducing race-window success and alerting on rogue DNS response patterns.
