"""Observational transport diagnostics; original API requests/retries unchanged.

Only exception classes, numeric OS codes and small categorical hints are logged.
No raw exception string, URL, proxy value, headers, credential or provider body.
"""
import json
from pathlib import Path
import socket
import ssl
import urllib.error
import urllib.request

from benchmarks.compact_deepseek.api import API, ProviderFault


def diagnostic(exc):
    chain, seen = [], set()
    current = exc
    while isinstance(current, BaseException) and id(current) not in seen and len(chain) < 6:
        seen.add(id(current))
        item = {"class": type(current).__name__}
        for key in ("errno", "winerror", "verify_code"):
            value = getattr(current, key, None)
            if type(value) is int: item[key] = value
        # No untrusted text enters the diagnostic; map only recognized categories.
        text = str(current).lower()
        for marker, category in (("getaddrinfo", "DNS"), ("name or service not known", "DNS"),
            ("certificate verify failed", "TLS_CERTIFICATE"), ("certificate_verify_failed", "TLS_CERTIFICATE"),
            ("timed out", "TIMEOUT"), ("connection reset", "CONNECTION_RESET"),
            ("connection refused", "CONNECTION_REFUSED"), ("tunnel connection failed", "PROXY_TUNNEL")):
            if marker in text: item["category"] = category; break
        chain.append(item)
        reason = getattr(current, "reason", None)
        current = reason if isinstance(reason, BaseException) else current.__context__
    return {"exception_chain": chain, "raw_text_retained": False}


class DiagnosticAPI(API):
    def __init__(self, path):
        super().__init__(path)
        self.failures = []

    def request(self, *args, **kwargs):
        try: return super().request(*args, **kwargs)
        except Exception as exc:
            self.failures.append(diagnostic(exc))
            raise


def connectivity():
    result = {"endpoint": "https://api.deepseek.com", "model_generation_calls": 0,
              "proxy_schemes_present": sorted(k for k in urllib.request.getproxies() if k in ("http", "https", "all"))}
    for name in ("dns", "direct_tls", "urllib_unauthenticated_https"):
        try:
            if name == "dns":
                result[name] = {"status": "PASS", "address_count": len(socket.getaddrinfo("api.deepseek.com", 443, type=socket.SOCK_STREAM))}
            elif name == "direct_tls":
                with socket.create_connection(("api.deepseek.com", 443), timeout=15) as conn:
                    with ssl.create_default_context().wrap_socket(conn, server_hostname="api.deepseek.com") as secure:
                        result[name] = {"status": "PASS", "tls_version": secure.version()}
            else:
                try:
                    with urllib.request.urlopen("https://api.deepseek.com", timeout=15) as response:
                        code = response.status
                except urllib.error.HTTPError as exc:
                    code = exc.code  # A received HTTP error still establishes transport.
                result[name] = {"status": "PASS_TRANSPORT", "http_status": code}
        except Exception as exc: result[name] = {"status": "FAIL", **diagnostic(exc)}
    return result


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    a = parser.parse_args()
    value = connectivity()
    with a.output.open("x", encoding="utf-8") as stream: json.dump(value, stream, indent=2)
    print(json.dumps(value))
