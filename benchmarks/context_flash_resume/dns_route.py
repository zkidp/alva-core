"""Process-local provider route: one validated DNS answer, normal HTTPS identity.

No system DNS edits, resolver installation, TLS bypass or request retry. Useful
only for the evidenced intermittent Windows resolver error. Expiry fails closed.
"""
import argparse
import http.client
import ipaddress
import json
from pathlib import Path
import socket
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from unittest.mock import patch

from benchmarks.context_flash_resume.transport import DiagnosticAPI, diagnostic

HOST = "api.deepseek.com"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.URLError("PROVIDER_REDIRECT_NOT_AUTHORIZED")


class Route:
    def __init__(self, *, address=None, seconds=300, clock=time.monotonic):
        if any(k in urllib.request.getproxies() for k in ("http", "https", "all")):
            raise RuntimeError("SCOPED_ROUTE_PROXY_ENVIRONMENT_UNSUPPORTED")
        if not 0 < seconds <= 300: raise ValueError("DNS_ROUTE_LIFETIME_BOUND")
        if address is None:
            answers = socket.getaddrinfo(HOST, 443, type=socket.SOCK_STREAM)
            address = answers[0][4][0]
        if not ipaddress.ip_address(address).is_global: raise RuntimeError("NONPUBLIC_PROVIDER_ADDRESS")
        self.address, self.clock, self.expires = address, clock, clock() + seconds
        self.context = ssl.create_default_context()
        route = self

        class HTTPS(urllib.request.HTTPSHandler):
            def https_open(self, req):
                route.check(req.full_url)
                return self.do_open(route.connection, req, context=route.context)
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), HTTPS(), NoRedirect())

    def check(self, url):
        parts = urllib.parse.urlsplit(url)
        if (parts.scheme, parts.hostname, parts.port or 443) != ("https", HOST, 443) or parts.username or parts.password:
            raise RuntimeError("PROVIDER_ORIGIN_NOT_AUTHORIZED")
        if self.clock() >= self.expires: raise RuntimeError("SCOPED_DNS_ROUTE_EXPIRED")

    def connection(self, host, **kwargs):
        self.check("https://" + host)
        conn = http.client.HTTPSConnection(host, **kwargs)
        route = self
        def connect(address, timeout=socket._GLOBAL_DEFAULT_TIMEOUT, source_address=None):
            if address != (HOST, 443): raise RuntimeError("CONNECTION_ORIGIN_MISMATCH")
            # HTTPSConnection keeps .host=HOST for SNI and certificate validation.
            # Only the TCP destination skips repeated flaky hostname resolution.
            return socket.create_connection((route.address, 443), timeout, source_address)
        conn._create_connection = connect
        return conn

    def open(self, request, timeout=90, **kwargs):
        self.check(request.full_url if hasattr(request, "full_url") else request)
        return self.opener.open(request, timeout=timeout)

    def probe(self):
        rows = []
        for _ in range(3):
            try:
                with self.open("https://" + HOST, timeout=15) as response: code = response.status
            except urllib.error.HTTPError as exc: code = exc.code
            rows.append({"http_status": code, "transport": "PASS", "tls_verification": "STANDARD_REQUIRED_HOSTNAME"})
        return {"status": "PASS", "requests": rows, "model_generation_calls": 0,
                "system_dns_modified": False, "provider_hostname": HOST, "max_route_seconds": self.expires - self.clock()}


class RoutedAPI(DiagnosticAPI):
    def __init__(self, credential_path, *, address=None):
        super().__init__(credential_path)
        self.route = Route(address=address)
        self.route_probe = self.route.probe()

    def request(self, *args, **kwargs):
        # The original API constructs the exact same URL/body/headers. One call
        # only, no retry. The scoped replacement is active only in this serial
        # controller API call and rejects every foreign origin and redirect.
        self.route.check("https://" + HOST)
        with patch("urllib.request.urlopen", self.route.open):
            return super().request(*args, **kwargs)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--address", help="Trusted operator's current public DNS answer; TLS hostname still mandatory")
    args = parser.parse_args()
    value = Route(address=args.address).probe()
    with args.output.open("x", encoding="utf-8") as stream: json.dump(value, stream, indent=2)
    print(json.dumps(value))
