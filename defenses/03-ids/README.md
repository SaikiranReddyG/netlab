# IDS Defense

## Sentinel-first run
```bash
sudo ip netns exec ns-def python3 /home/reddy/codex-workspace/sentinel/src/main.py \
  -i veth-def \
  -c /home/reddy/codex-workspace/sentinel/config.yaml \
  --no-dashboard
```

To use lab-specific rules, run:
```bash
sudo ip netns exec ns-def python3 /home/reddy/codex-workspace/netlab/defenses/01-arp-defense/detect.py \
  --iface veth-def \
  --sentinel-path /home/reddy/codex-workspace/sentinel \
  --rules /home/reddy/codex-workspace/netlab/defenses/03-ids/sentinel-rules.yaml
```

## Suricata supplemental rules
Load `suricata-custom.rules` if Suricata is installed in your environment.
