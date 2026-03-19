# Netlab Testing & Verification Guide

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Lab Initialization](#lab-initialization)
3. [Exercise-by-Exercise Testing](#exercise-by-exercise-testing)
4. [Automated Validation](#automated-validation)
5. [Troubleshooting](#troubleshooting)
6. [Advanced Testing](#advanced-testing)

---

## Prerequisites

### System Requirements
- Linux host with sudo/root access
- Kernel support for namespaces and bridging
- Minimum 2GB free RAM

### Required Tools
```bash
# Recommended (auto-detects apt-get or pacman)
sudo ./lab/install-deps.sh

# Debian/Ubuntu (manual)
sudo apt-get update
sudo apt-get install -y iproute2 bridge-utils tcpdump dnsmasq hping3 nftables curl dnsutils python3 python3-pip python3-scapy python3-yaml

# Arch Linux (manual)
sudo pacman -Sy --noconfirm iproute2 bridge-utils tcpdump dnsmasq hping nftables curl bind python python-pip python-scapy python-yaml

# Optional: network analysis
# Debian/Ubuntu: sudo apt-get install -y wireshark tshark
# Arch Linux:    sudo pacman -Sy --noconfirm wireshark-qt tshark
```

### Installation Verification
```bash
# Check all required tools are present
command -v ip && echo "✓ ip"
command -v bridge && echo "✓ bridge/iproute2"
command -v tcpdump && echo "✓ tcpdump"
command -v dnsmasq && echo "✓ dnsmasq"
command -v hping3 && echo "✓ hping3"
command -v nft && echo "✓ nftables"
python3 -c "import scapy.all" && echo "✓ scapy"
python3 -c "import yaml" && echo "✓ pyyaml"
```

---

## Lab Initialization

### 1. Start the Lab
```bash
cd /home/reddy/codex-workspace/netlab
sudo ./lab/setup.sh
```

**Expected Output:**
```
[+] Netlab setup complete
    Namespaces: ns-atk, ns-def, ns-srv, ns-dns
    Bridge: br-lab (10.0.0.1/24)
    Service logs: /path/to/.netlab-runtime
```

### 2. Verify Lab Status
```bash
sudo ./lab/status.sh
```

**Expected Output:**
- All 4 namespaces listed
- Bridge interface `br-lab` in UP state
- All veth pairs connected
- HTTP and DNS services running

### 3. Quick Connectivity Check
```bash
# Test HTTP connectivity
sudo ip netns exec ns-atk curl -s http://10.0.0.10

# Test DNS resolution
sudo ip netns exec ns-atk nslookup target.lab 10.0.0.53

# Test ping from different namespaces
sudo ip netns exec ns-atk ping -c 1 10.0.0.10
sudo ip netns exec ns-def ping -c 1 10.0.0.10
```

**Expected Response:**
- HTTP: HTML response from target server
- DNS: `Name: target.lab, Address: 10.0.0.10`
- PING: 1 packet received from both namespaces

### 4. Check Service Logs
```bash
tail -20 .netlab-runtime/http-server.log
tail -20 .netlab-runtime/dnsmasq.log
```

---

## Exercise-by-Exercise Testing

### Exercise 01: ARP Spoofing

#### 1a. Baseline Capture
```bash
# Terminal 1: Start capture on server namespace
sudo ip netns exec ns-srv tcpdump -ni veth-srv arp -w captures/01-arp-baseline.pcap &

# Terminal 2: Trigger ARP activity
sudo ip netns exec ns-srv ip neigh flush 10.0.0.1 dev veth-srv
sudo ip netns exec ns-srv ping -c 1 10.0.0.1

# Let capture run for 5 seconds, then kill
pkill -f "tcpdump -ni veth-srv"
```

**Expected:** No spoofed ARP entries in baseline capture

#### 1b. Execute Attack
```bash
# Make sure IP forwarding is enabled
sudo ip netns exec ns-atk sysctl -w net.ipv4.ip_forward=1 > /dev/null

# Start attack from attacker namespace
sudo ip netns exec ns-atk python3 attacks/01-arp-spoof/attack.py \
  --iface veth-atk \
  --target-ip 10.0.0.10 \
  --gateway-ip 10.0.0.1 \
  --interval 0.5 &

ATTACK_PID=$!

# Let attack run for 5 seconds
sleep 5

# Verify neighbor table changed
sudo ip netns exec ns-srv ip neigh show 10.0.0.1 dev veth-srv

# Kill attack
kill $ATTACK_PID 2>/dev/null || true
sleep 1

# Verify neighbor table restored
sudo ip netns exec ns-srv ip neigh show 10.0.0.1 dev veth-srv
```

**Expected Results:**
- During attack: Gateway MAC changes to attacker's MAC (32:28:a6:47:7a:f5)
- After attack: Gateway MAC reverts to original

#### 1c. Verify Capture Evidence
```bash
tcpdump -nn -r captures/01-arp-spoof.pcap | head -30
```

**Expected:** ARP replies showing attacker MAC address

#### 1d. Test Defense
```bash
# Apply static ARP binding
sudo ./defenses/01-arp-defense/static-arp.sh

# Re-run attack with same command
sudo ip netns exec ns-atk python3 attacks/01-arp-spoof/attack.py \
  --iface veth-atk \
  --target-ip 10.0.0.10 \
  --gateway-ip 10.0.0.1 \
  --interval 0.5 &

ATTACK_PID=$!
sleep 5

# Check neighbor table - should NOT change
sudo ip netns exec ns-srv ip neigh show

kill $ATTACK_PID 2>/dev/null || true
```

**Expected:** Neighbor table remains static, attack has no effect

---

### Exercise 02: Man-in-the-Middle (MITM)

#### 2a. Setup Capture
```bash
# Terminal 1: Start packet capture on attacker's interface
sudo ip netns exec ns-atk tcpdump -ni veth-atk tcp port 80 -w captures/02-mitm.pcap &

CAPTURE_PID=$!
sleep 1
```

#### 2b. Position Attacker
```bash
# Terminal 2: Enable IP forwarding and run bidirectional ARP poisoning
sudo ip netns exec ns-atk sysctl -w net.ipv4.ip_forward=1 > /dev/null

# Poison victim (ns-def, 10.0.0.3) to think attacker is gateway
sudo ip netns exec ns-atk python3 attacks/01-arp-spoof/attack.py \
  --iface veth-atk \
  --target-ip 10.0.0.3 \
  --gateway-ip 10.0.0.10 \
  --interval 0.3 &

PID1=$!
sleep 1

# Poison server (ns-srv, 10.0.0.10) to think attacker is victim
sudo ip netns exec ns-atk python3 attacks/01-arp-spoof/attack.py \
  --iface veth-atk \
  --target-ip 10.0.0.10 \
  --gateway-ip 10.0.0.3 \
  --interval 0.3 &

PID2=$!
sleep 2
```

#### 2c. Generate Traffic
```bash
# Terminal 3: Generate HTTP requests from victim
for i in {1..10}; do
  sudo ip netns exec ns-def curl -s http://10.0.0.10 > /dev/null
  sleep 0.5
done
```

#### 2d. Stop Capture
```bash
# Stop all processes
kill $CAPTURE_PID $PID1 $PID2 2>/dev/null || true
sleep 2
```

#### 2e. Analyze Capture
```bash
# View PCAP summary
ls -lh captures/02-mitm.pcap
tcpdump -nn -r captures/02-mitm.pcap | grep -E "GET|HTTP" | head -10
```

**Expected:** Plaintext HTTP GET requests visible in PCAP

#### 2f. Test Firewall Defense
```bash
# Apply nftables firewall
sudo ./defenses/02-firewall/apply.sh

# Verify rules are active
sudo ip netns exec ns-srv nft list ruleset | head -20

# Attempt same attack - verify restricted traffic
# (Follow same steps 2a-2d above)
```

---

### Exercise 03: DNS Poisoning

#### 3a. Setup
```bash
# Enable forwarding on attacker
sudo ip netns exec ns-atk sysctl -w net.ipv4.ip_forward=1 > /dev/null

# Position attacker MITM (same as Exercise 02)
sudo ip netns exec ns-atk python3 attacks/01-arp-spoof/attack.py \
  --iface veth-atk \
  --target-ip 10.0.0.3 \
  --gateway-ip 10.0.0.53 \
  --interval 0.3 &

PID1=$!
sleep 1

sudo ip netns exec ns-atk python3 attacks/01-arp-spoof/attack.py \
  --iface veth-atk \
  --target-ip 10.0.0.53 \
  --gateway-ip 10.0.0.3 \
  --interval 0.3 &

PID2=$!
sleep 2
```

#### 3b. Start DNS Poison Attack
```bash
# Terminal 2: Start DNS poisoning
sudo ip netns exec ns-atk timeout 30 python3 attacks/03-dns-poison/poison.py &

POISON_PID=$!
sleep 1
```

#### 3c. Start Capture
```bash
# Terminal 3: Capture DNS traffic
sudo ip netns exec ns-atk tcpdump -ni veth-atk udp port 53 -w captures/03-dns-poison.pcap &

CAPTURE_PID=$!
sleep 1
```

#### 3d. Generate DNS Queries
```bash
# Terminal 4: Generate DNS lookups from victim
for i in {1..20}; do
  sudo ip netns exec ns-def nslookup target.lab 10.0.0.53
  sleep 0.5
done
```

#### 3e. Stop and Analyze
```bash
# Stop all processes
kill $POISON_PID $CAPTURE_PID $PID1 $PID2 2>/dev/null || true
sleep 2

# View capture
tcpdump -nn -r captures/03-dns-poison.pcap | grep -E "A\?" | head -10
```

**Expected:** DNS A record queries visible, with mix of legitimate (10.0.0.10) and spoofed (10.0.0.2) responses

---

### Exercise 04: SYN Flood

#### 4a. Baseline HTTP Performance
```bash
# Normal request (no attack)
time sudo ip netns exec ns-atk curl -s http://10.0.0.10 | wc -c
```

#### 4b. Start Flood Attack
```bash
# Terminal 1: Start SYN flood
sudo ./attacks/04-syn-flood/flood.sh

# For unlimited flood (careful!):
# sudo ./attacks/04-syn-flood/flood.sh --flood
```

#### 4c. Monitor Impact
```bash
# Terminal 2: Test connectivity during flood
for i in {1..5}; do
  time sudo ip netns exec ns-atk curl -s http://10.0.0.10 --max-time 2 > /dev/null
  sleep 0.5
done

# Check netstat on target server
sudo ip netns exec ns-srv netstat -n | grep SYN_RECV | wc -l
```

#### 4d. Capture Evidence
```bash
# Capture SYN packets during flood
timeout 30 sudo ip netns exec ns-atk tcpdump -ni veth-atk "tcp[tcpflags] & tcp-syn != 0" -w captures/04-syn-flood.pcap &

# Re-run flood in another terminal
sudo ./attacks/04-syn-flood/flood.sh

# Check capture
ls -lh captures/04-syn-flood.pcap
tcpdump -nn -r captures/04-syn-flood.pcap | head -20
```

#### 4e. Apply Protection
```bash
# Enable kernel hardening
sudo ./defenses/04-hardening/sysctl.sh

# Verify tcp_syncookies enabled
sudo ip netns exec ns-srv sysctl net.ipv4.tcp_syncookies

# Apply rate-limit firewall rules (from Exercise 02 defense)
sudo ./defenses/02-firewall/apply.sh

# Verify firewall rules
sudo ip netns exec ns-srv nft list ruleset | grep -A 5 "tcp flags"
```

#### 4f. Test Defense
```bash
# Re-run flood attack
sudo ./attacks/04-syn-flood/flood.sh

# HTTP should still respond (with possible delays)
sudo ip netns exec ns-atk curl -s http://10.0.0.10 --max-time 5
```

**Expected:** HTTP responses continue despite SYN flood

---

## Automated Validation

### Run Full Lab Validation
```bash
# Syntax check (doesn't require execution)
bash -n lab/validate_phase2.sh

# Full execution with appropriate cleanup
sudo ./lab/validate_phase2.sh
```

### Quick Smoke Test
```bash
sudo ./lab/teardown.sh
sudo ./lab/setup.sh

# Verify connectivity
sudo ip netns exec ns-atk curl -s http://10.0.0.10 | head -5
sudo ip netns exec ns-atk nslookup target.lab 10.0.0.53
sudo ip netns exec ns-atk ping -c 1 10.0.0.10

sudo ./lab/teardown.sh
echo "✓ Smoke test passed"
```

---

## Troubleshooting

### Issue: "Run as root" error
```bash
# Solution: Always use sudo
sudo ./lab/setup.sh
sudo ./lab/status.sh
```

### Issue: Missing tools
```bash
# Check what's missing
./lab/setup.sh 2>&1 | grep "\[!\]"

# Install missing packages (auto-detects apt-get/pacman)
sudo ./lab/install-deps.sh
```

### Issue: DNS returns NXDOMAIN
```bash
# Check dnsmasq is running
ps aux | grep dnsmasq

# Check DNS logs
tail -30 .netlab-runtime/dnsmasq.log

# Manual test from DNS namespace
sudo ip netns exec ns-dns dig @127.0.0.1 target.lab
```

### Issue: ARP poisoning not working
```bash
# Verify IP forwarding enabled
sudo ip netns exec ns-atk cat /proc/sys/net/ipv4/ip_forward
# Should be 1

# Enable if not
sudo ip netns exec ns-atk sysctl -w net.ipv4.ip_forward=1

# Check Scapy can send packets
sudo ip netns exec ns-atk python3 -c "from scapy.all import send; print('scapy OK')"
```

### Issue: Capture shows no packets
```bash
# Increase capture timeout
timeout 30 sudo ip netns exec ns-atk tcpdump -ni veth-atk -w capture.pcap

# Check interface is correct
sudo ip netns list
sudo ip netns exec ns-atk ip link show

# Verify traffic on correct port (e.g., port 80)
sudo ip netns exec ns-atk tcpdump -ni veth-atk tcp port 80 -vv
```

### Issue: Services won't start
```bash
# Check service logs
tail -50 .netlab-runtime/http-server.log
tail -50 .netlab-runtime/dnsmasq.log

# Try manual start in namespace
sudo ip netns exec ns-dns dnsmasq --help

# Verify ports not bound by host
sudo netstat -tulpn | grep ":80\|:53"
```

---

## Advanced Testing

### Performance Testing
```bash
# Baseline latency (no attack)
for i in {1..100}; do
  time sudo ip netns exec ns-atk curl -s http://10.0.0.10 > /dev/null 2>&1
done | grep real | awk '{print $2}' | sort -n | tail -5

# Under SYN flood
# (Run flood in one terminal)
# Run above command in another
```

### Comparison Testing
```bash
# Capture before defense
sudo ip netns exec ns-def curl -s http://10.0.0.10 > /dev/null
sudo ip netns exec ns-atk tcpdump -ni veth-atk tcp port 80 -c 100 -w before-defense.pcap

# Apply defense
sudo ./defenses/02-firewall/apply.sh

# Capture after defense
sudo ip netns exec ns-def curl -s http://10.0.0.10 > /dev/null
sudo ip netns exec ns-atk tcpdump -ni veth-atk tcp port 80 -c 100 -w after-defense.pcap

# Compare packet counts
echo "Before: $(tcpdump -r before-defense.pcap 2>/dev/null | wc -l)"
echo "After: $(tcpdump -r after-defense.pcap 2>/dev/null | wc -l)"
```

### Sentinel Integration Testing
```bash
# If Sentinel is available
export SENTINEL_PATH=/home/reddy/codex-workspace/sentinel

# Run detection in background
python3 defenses/01-arp-defense/detect.py &
DETECT_PID=$!

# Execute attack
sudo ip netns exec ns-atk python3 attacks/01-arp-spoof/attack.py \
  --iface veth-atk \
  --target-ip 10.0.0.10 \
  --gateway-ip 10.0.0.1 \
  --interval 0.5 &

sleep 10

# Check detections reported
kill $DETECT_PID 2>/dev/null || true
```

---

## Cleanup

### Clean Single Exercise
```bash
# Stop services and remove runtime artifacts
sudo ./lab/teardown.sh
rm -rf .netlab-runtime/
```

### Full Clean (keep code)
```bash
sudo ./lab/teardown.sh
rm -rf .netlab-runtime/ captures/*.pcap
git status  # Verify no important files deleted
```

### Reset to Default State
```bash
sudo ./lab/teardown.sh
git checkout -- .
git clean -fd
```

---

## Appendix: Lab Topology Reference

```
                       Bridge: br-lab (10.0.0.1/24)
                              |
           ___________________+_____________________
           |                  |                    |
        veth-atk-br       veth-def-br          veth-srv-br      veth-dns-br
           |                  |                    |                |
        +-----------+    +-----------+         +-----------+    +-----------+
        | ns-atk    |    | ns-def    |         | ns-srv    |    | ns-dns    |
        |10.0.0.2   |    |10.0.0.3   |         |10.0.0.10  |    |10.0.0.53  |
        +-----------+    +-----------+         +-----------+    +-----------+
        [Attacker]      [Defender]             [Target]         [DNS]
                                               [HTTP:80]         [dnsmasq]
```

### IP Address Reference
| Namespace | IP Address | Role | Service |
|-----------|-----------|------|---------|
| ns-atk    | 10.0.0.2  | Attacker | - |
| ns-def    | 10.0.0.3  | Defender/Victim | - |
| ns-srv    | 10.0.0.10 | Target Server | HTTP (port 80) |
| ns-dns    | 10.0.0.53 | DNS Server | dnsmasq (port 53) |
| br-lab    | 10.0.0.1  | Gateway/Bridge | - |

---

## Success Criteria

A successful test run includes:
- ✔ Lab starts without errors: `sudo ./lab/setup.sh`
- ✔ All namespaces created: `sudo ./lab/status.sh`
- ✔ HTTP connectivity works: `sudo ip netns exec ns-atk curl -s http://10.0.0.10`
- ✔ DNS resolution works: `sudo ip netns exec ns-atk nslookup target.lab 10.0.0.53`
- ✔ ARP attack captures valid evidence: PCAP shows spoofed MAC
- ✔ MITM captures plaintext HTTP: PCAP shows GET/HTTP response
- ✔ DNS attack shows injected responses: PCAP shows spoofed A records
- ✔ SYN flood executes without error: 3000+ packets sent
- ✔ Defenses activate successfully: Firewall rules, sysctl, ARP binding apply
- ✔ Lab teardown completes: `sudo ./lab/teardown.sh`
