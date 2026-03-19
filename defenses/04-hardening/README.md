# Kernel Hardening

## Apply to server namespace
```bash
sudo ./defenses/04-hardening/sysctl.sh ns-srv
```

## Apply to all namespaces
```bash
sudo ./defenses/04-hardening/sysctl.sh --all
```

## Tuned parameters
- `rp_filter=1`
- `arp_ignore=2`
- `arp_announce=2`
- `tcp_syncookies=1`
- redirect controls disabled
