"""Bounded public-page fetch with pinned DNS and redirect validation."""
import http.client
import ipaddress
import socket
import time
from urllib.parse import urljoin, urlsplit


def resolve_public(url):
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
        raise ValueError("Only public http/https pages without credentials can be imported.")
    port = parts.port or (443 if parts.scheme == "https" else 80)
    if port not in {80, 443}:
        raise ValueError("Only standard web ports are supported.")
    addresses = socket.getaddrinfo(parts.hostname, port, type=socket.SOCK_STREAM)
    ips = {item[4][0] for item in addresses}
    if not ips or any(not ipaddress.ip_address(ip).is_global for ip in ips):
        raise ValueError("Private and local network addresses cannot be imported.")
    return parts, port, sorted(ips)[0]


def fetch_page(url):
    deadline = time.monotonic() + 60
    redirects = []
    for _ in range(5):
        parts, port, ip = resolve_public(url)
        connection_type = http.client.HTTPSConnection if parts.scheme == "https" else http.client.HTTPConnection
        connection = connection_type(parts.hostname, port, timeout=15)
        # Connect to the validated IP, retaining the hostname for TLS verification.
        connection._create_connection = lambda address, timeout, source_address=None: socket.create_connection((ip, port), timeout, source_address)
        try:
            target = (parts.path or "/") + ("?" + parts.query if parts.query else "")
            connection.request("GET", target, headers={"User-Agent": "StudyBuddy/0.1 (local study import)",
                                                       "Accept": "text/html,text/plain", "Accept-Encoding": "identity"})
            response = connection.getresponse()
            if response.status in {301, 302, 303, 307, 308}:
                location = response.getheader("Location")
                if not location:
                    raise ValueError("The page redirected without a destination.")
                redirects.append(url)
                url = urljoin(url, location)
                continue
            if response.status != 200:
                raise ValueError(f"Website returned HTTP {response.status}.")
            content_type = response.getheader("Content-Type", "")
            if not any(kind in content_type.lower() for kind in ("text/html", "text/plain", "application/xhtml+xml")):
                raise ValueError("This URL is not an HTML or plain-text page.")
            if response.getheader("Content-Encoding", "identity").lower() != "identity":
                raise ValueError("The website returned unsupported compressed content.")
            body = bytearray()
            while True:
                if time.monotonic() > deadline:
                    raise ValueError("Page download timed out.")
                block = response.read(65536)
                if not block:
                    break
                body.extend(block)
                if len(body) > 5 * 1024 * 1024:
                    raise ValueError("Page exceeds the 5 MB import limit.")
            return bytes(body), {"final_url": url, "redirects": redirects, "content_type": content_type,
                                 "headers": dict(response.getheaders()), "status": response.status}
        finally:
            connection.close()
    raise ValueError("The page redirected too many times.")
