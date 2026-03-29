# ARP Defense

## Static ARP Lock
```bash
sudo ./defenses/01-arp-defense/static-arp.sh ns-srv veth-srv
```

This pins gateway and DNS ARP entries as permanent in the selected namespace.

## Detection (Sentinel-first)
```bash
sudo ip netns exec ns-def python3 defenses/01-arp-defense/detect.py \
  --iface veth-def \
  --sentinel-path ../sentinel
```

## Detection fallback mode
```bash
sudo ip netns exec ns-def python3 defenses/01-arp-defense/detect.py \
  --iface veth-def --fallback
```
