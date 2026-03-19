# Exercise 04: SYN Flood

## Setup
- Target HTTP service running on `10.0.0.10:80`

## Attack Steps
1. Run bounded flood script.
2. Observe service responsiveness and packet rate.

## Evidence
- Capture: `captures/04-syn-flood.pcap`
- Connection impact observations: _add here_

## Defense Applied
- nftables SYN rate limiting
- kernel hardening (`tcp_syncookies`)

## Result After Defense
- _document mitigation effectiveness_
