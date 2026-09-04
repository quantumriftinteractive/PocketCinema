"""Host capability discovery used by the desktop manager and tests."""
from dataclasses import dataclass
import ipaddress
import os
from pathlib import Path
import shutil
import socket
import urllib.error
import urllib.request

from .config import ConfigurationError, validate_stremio_service_url


@dataclass(frozen=True)
class ToolStatus:
    path: str
    available: bool
    source: str


@dataclass(frozen=True)
class ServiceStatus:
    configured: bool
    reachable: bool
    message: str


def detect_tool(name, manual_path=""):
    if manual_path:
        path = Path(manual_path).expanduser()
        available = path.is_file() and os.access(path, os.X_OK)
        return ToolStatus(str(path), available, "manual")
    found = shutil.which(name)
    return ToolStatus(found or "", bool(found), "PATH" if found else "missing")


def local_addresses():
    """Return unique usable addresses without inferring a network provider."""
    values = [("Loopback", "127.0.0.1")]
    try:
        records = socket.getaddrinfo(socket.gethostname(), None, type=socket.SOCK_STREAM)
    except OSError:
        records = []
    seen = {"127.0.0.1"}
    for record in records:
        address = record[4][0]
        if address in seen or not _usable_device_address(address):
            continue
        seen.add(address)
        values.append((socket.gethostname(), address))
    return values


def preferred_local_address(addresses=None):
    """Choose the first non-loopback host address without naming its transport."""
    addresses = local_addresses() if addresses is None else addresses
    for _, address in addresses:
        if _usable_device_address(address):
            return address
    return ""


def _usable_device_address(address):
    try:
        candidate = ipaddress.ip_address(address.split("%", 1)[0])
    except ValueError:
        return False
    return not (
        candidate.is_loopback
        or candidate.is_link_local
        or candidate.is_multicast
        or candidate.is_unspecified
    )


def probe_stremio_service(url, timeout=2):
    try:
        url = validate_stremio_service_url(url)
    except ConfigurationError as exc:
        return ServiceStatus(False, False, str(exc))
    try:
        request = urllib.request.Request(url + "/settings", headers={"User-Agent": "PocketCinema/1.0"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if not 200 <= response.status < 300:
                raise OSError("unexpected HTTP response")
    except (OSError, urllib.error.URLError, urllib.error.HTTPError):
        return ServiceStatus(True, False, "Configured Stremio Service is currently unreachable from this machine.")
    return ServiceStatus(True, True, "Configured Stremio Service is reachable.")
