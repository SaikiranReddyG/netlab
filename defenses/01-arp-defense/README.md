# ARP Defense

## Static ARP Lock
```bash
sudo ./defenses/01-arp-defense/static-arp.sh ns-srv veth-srv
```

This pins gateway and DNS ARP entries as permanent in the selected namespace.

## Detection
```bash
sudo ip netns exec ns-def python3 defenses/01-arp-defense/detect.py \
  --iface veth-def
```

If Sentinel is installed separately, point it at netlab event streams via the `http_post` output. See `CONTRACT.md` for the event schema; otherwise the detector falls back to the local Scapy-based mode.

## Detection fallback mode
```bash
sudo ip netns exec ns-def python3 defenses/01-arp-defense/detect.py \
  --iface veth-def --fallback
```
