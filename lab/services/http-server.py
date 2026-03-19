#!/usr/bin/env python3
"""Minimal HTTP service used as the lab target."""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime, timezone


class Handler(BaseHTTPRequestHandler):
    server_version = "NetlabHTTP/1.0"

    def do_GET(self) -> None:  # noqa: N802 (HTTP API naming)
        body = (
            "<html><body>"
            "<h1>Netlab Target Server</h1>"
            f"<p>Path: {self.path}</p>"
            f"<p>UTC: {datetime.now(timezone.utc).isoformat()}</p>"
            "</body></html>"
        ).encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"[http-server] {self.address_string()} - {fmt % args}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Netlab HTTP service")
    p.add_argument("--host", default="10.0.0.10", help="Listen host")
    p.add_argument("--port", type=int, default=80, help="Listen port")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    httpd = HTTPServer((args.host, args.port), Handler)
    print(f"[http-server] listening on {args.host}:{args.port}")
    httpd.serve_forever()


if __name__ == "__main__":
    main()