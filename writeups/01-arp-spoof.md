# Exercise 01: ARP Spoof

## Setup
- Lab started with `sudo ./lab/setup.sh`
- Baseline gateway neighbor in target namespace:
	- `10.0.0.1 lladdr aa:af:c4:0e:00:a2 REACHABLE`

## Attack Steps
1. Run Scapy spoof attack in attacker namespace:
	- `sudo ip netns exec ns-atk python3 attacks/01-arp-spoof/attack.py --iface veth-atk --target-ip 10.0.0.10 --gateway-ip 10.0.0.1 --interval 0.5`
2. Check gateway mapping during attack from target namespace:
	- `sudo ip netns exec ns-srv ip neigh show 10.0.0.1 dev veth-srv`
3. Stop attack and confirm mapping restoration.

## Evidence
- Capture: `captures/01-arp-spoof.pcap`
- Neighbor table transition observed:
	- `[before] 10.0.0.1 lladdr aa:af:c4:0e:00:a2 REACHABLE`
	- `[during] 10.0.0.1 lladdr 32:28:a6:47:7a:f5 REACHABLE`
	- `[after]  10.0.0.1 lladdr aa:af:c4:0e:00:a2 REACHABLE`
- PCAP sample confirms spoofed ARP replies:
	- `ARP, Reply 10.0.0.1 is-at 32:28:a6:47:7a:f5`
	- Multiple repeated replies observed while attack was active.

## Defense Applied
- Static ARP (`defenses/01-arp-defense/static-arp.sh`)
- Detector (`defenses/01-arp-defense/detect.py`)

## Result After Defense
- Static ARP lock and detector controls are in place, and replay checks confirm neighbor-table poisoning attempts are surfaced and constrained.
