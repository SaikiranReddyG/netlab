# ARP Spoof Attack

## Goal
Poison ARP caches so `ns-srv` treats the attacker as the gateway (`10.0.0.1`).

## Run (tool wrapper)
```bash
sudo ./attacks/01-arp-spoof/attack.sh
```

## Run (Scapy)
```bash
sudo ip netns exec ns-atk python3 /home/reddy/codex-workspace/netlab/attacks/01-arp-spoof/attack.py --iface veth-atk
```

## Verify
```bash
sudo ip netns exec ns-srv ip neigh show 10.0.0.1
```
Expected: gateway IP points to attacker MAC during the attack.

## Capture
```bash
sudo ip netns exec ns-srv tcpdump -ni veth-srv arp -w /home/reddy/codex-workspace/netlab/captures/01-arp-spoof.pcap
```
