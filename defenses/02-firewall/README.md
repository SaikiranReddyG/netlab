# Firewall Defense (nftables)

## Apply rules in defender namespace
```bash
sudo ./defenses/02-firewall/apply.sh ns-def
```

## Optional: apply in server namespace
```bash
sudo ./defenses/02-firewall/apply.sh ns-srv
```

## Expected effect
1. Spoofed/invalid traffic is dropped.
2. SYN rates are limited.
3. Established traffic continues.
