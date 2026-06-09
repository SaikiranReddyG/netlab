# IDS Defense

## Event-stream integration
The IDS emits and consumes the same event schema described in `CONTRACT.md`.
Use the `http_post` output to feed external tooling if you want to replay or
analyze events outside netlab.

## Suricata supplemental rules
Load `suricata-custom.rules` if Suricata is installed in your environment.
