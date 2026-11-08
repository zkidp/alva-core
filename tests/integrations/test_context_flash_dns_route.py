import ssl
import unittest
from unittest.mock import patch, Mock

from benchmarks.context_flash_resume.dns_route import Route, HOST, NoRedirect, RoutedAPI
import urllib.error


class RouteTests(unittest.TestCase):
    def route(self):
        with patch("urllib.request.getproxies", return_value={}), patch("socket.getaddrinfo", return_value=[(2,1,6,"",("8.8.8.8",443))]):
            return Route(clock=lambda: 100)

    def test_hostname_and_tls_verification_remain_intact(self):
        route = self.route()
        self.assertTrue(route.context.check_hostname)
        self.assertEqual(route.context.verify_mode, ssl.CERT_REQUIRED)
        conn = route.connection(HOST, context=route.context)
        self.assertEqual(conn.host, HOST)
        with patch("socket.create_connection", return_value=Mock()) as connect:
            conn._create_connection((HOST,443), 20)
            connect.assert_called_once_with(("8.8.8.8",443),20,None)
        with self.assertRaises(RuntimeError): conn._create_connection(("other.invalid",443))

    def test_foreign_origins_and_expiry_fail_closed(self):
        route = self.route()
        for url in ("http://" + HOST, "https://other.invalid", "https://" + HOST + ":444", "https://user:secret@" + HOST):
            with self.assertRaises(RuntimeError): route.check(url)
        route.expires = 99
        with self.assertRaises(RuntimeError): route.check("https://" + HOST)

    def test_proxy_not_silently_bypassed(self):
        with patch("urllib.request.getproxies", return_value={"https":"not-recorded"}):
            with self.assertRaises(RuntimeError): Route()

    def test_redirect_and_private_address_rejected(self):
        with self.assertRaises(urllib.error.URLError): NoRedirect().redirect_request(None,None,302,"",{},"https://other.invalid")
        with patch("urllib.request.getproxies", return_value={}):
            with self.assertRaises(RuntimeError): Route(address="127.0.0.1")

    def test_routed_api_does_not_replay_failed_requests(self):
        client = object.__new__(RoutedAPI)
        client.route = Mock()
        client.failures = []
        body = {"model": "deepseek-flash"}
        with patch("benchmarks.compact_deepseek.api.API.request", side_effect=ssl.SSLCertVerificationError(1,"certificate verify failed")) as request:
            with self.assertRaises(ssl.SSLCertVerificationError): client.request("/chat/completions", body, timeout=90)
        request.assert_called_once_with("/chat/completions", body, timeout=90)
        self.assertEqual(client.failures[0]["exception_chain"][0]["category"], "TLS_CERTIFICATE")


if __name__ == "__main__": unittest.main()
