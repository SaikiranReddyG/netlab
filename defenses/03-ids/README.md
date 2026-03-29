# IDS Defense

## Sentinel-first run
```bash
sudo ip netns exec ns-def python3 ../sentinel/src/main.py \
  -i veth-def \
  -c ../sentinel/config.yaml \
  --no-dashboard
```

To use lab-specific rules, run:
```bash
sudo ip netns exec ns-def python3 defenses/01-arp-defense/detect.py \
  --iface veth-def \
  --sentinel-path ../sentinel \
  --rules defenses/03-ids/sentinel-rules.yaml
```

## Suricata supplemental rules
Load `suricata-custom.rules` if Suricata is installed in your environment.
