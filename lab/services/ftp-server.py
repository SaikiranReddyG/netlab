#!/usr/bin/env python3
"""Optional FTP-like placeholder service for future exercises.

This file intentionally provides a tiny TCP server banner rather than a full FTP
implementation to keep the initial project scope focused on core attacks.
"""

from __future__ import annotations

import argparse
import socket


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Optional Netlab FTP placeholder")
    p.add_argument("--host", default="10.0.0.10")
    p.add_argument("--port", type=int, default=2121)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((args.host, args.port))
        sock.listen(5)
        print(f"[ftp-placeholder] listening on {args.host}:{args.port}")
        while True:
            conn, addr = sock.accept()
            with conn:
                conn.sendall(b"220 netlab ftp placeholder\\r\\n")
                _ = conn.recv(1024)
                conn.sendall(b"221 goodbye\\r\\n")
                print(f"[ftp-placeholder] served {addr[0]}:{addr[1]}")


if __name__ == "__main__":
    main()
