# SYN Flood

## Goal
Exhaust target TCP connection handling with many SYN packets.

## Bounded run (recommended)
```bash
sudo ./attacks/04-syn-flood/flood.sh
```

## Unlimited flood mode
```bash
sudo ./attacks/04-syn-flood/flood.sh --flood
```

## Scapy version
```bash
sudo ip netns exec ns-atk python3 attacks/04-syn-flood/flood.py \
  --target-ip 10.0.0.10 --target-port 80 --count 5000 --pps 800
```

## Capture
```bash
sudo ip netns exec ns-srv tcpdump -ni veth-srv 'tcp[tcpflags] & tcp-syn != 0' -w captures/04-syn-flood.pcap
```
