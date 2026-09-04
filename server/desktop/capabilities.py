"""Host capability discovery used by the desktop manager and tests."""
from dataclasses import dataclass
import ipaddress
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import urllib.error
import urllib.request

from .config import ConfigurationError, validate_stremio_service_url
from .config import DeviceEndpoint


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
    """Compatibility view of concrete Local network addresses."""
    return [("Loopback", "127.0.0.1")] + [
        (endpoint.interface or endpoint.label, endpoint.address)
        for endpoint in device_endpoints()
        if endpoint.kind == "local"
    ]


def _ifconfig_addresses(output):
    """Parse active IPv4 addresses from macOS ``ifconfig`` output.

    This reads operating-system interface information only.  It does not call,
    configure, or inspect any network-provider process or state.
    """
    current = ""
    active = False
    candidates = []
    for raw_line in output.splitlines():
        if raw_line and not raw_line[0].isspace() and ":" in raw_line:
            current = raw_line.split(":", 1)[0]
            active = "UP" in raw_line and "RUNNING" in raw_line
            continue
        line = raw_line.strip()
        if line == "status: active":
            active = True
            continue
        if not active or not line.startswith("inet "):
            continue
        address = line.split()[1]
        if _usable_device_address(address):
            candidates.append((current, address))
    return candidates


def _hostname_addresses():
    try:
        records = socket.getaddrinfo(socket.gethostname(), None, type=socket.SOCK_STREAM)
    except OSError:
        records = []
    return [(socket.gethostname(), record[4][0]) for record in records]


def host_interface_addresses(platform=None, ifconfig_output=None):
    """Return usable host IPv4 candidates with their OS interface identity."""
    platform = platform or sys.platform
    if platform == "darwin":
        if ifconfig_output is None:
            try:
                ifconfig_output = subprocess.run(
                    ["/sbin/ifconfig", "-a"], check=False, text=True,
                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                ).stdout
            except OSError:
                ifconfig_output = ""
        records = _ifconfig_addresses(ifconfig_output)
    else:
        records = _hostname_addresses()
    seen = set()
    return tuple(
        (interface, address)
        for interface, address in records
        if _usable_device_address(address) and not (address in seen or seen.add(address))
    )


def _tailnet_interface_address(interface, address):
    """Recognize the host's active tailnet-style tunnel address as interface data.

    The check deliberately requires both a tunnel-like interface and the shared
    tailnet IPv4 range; it neither contacts nor controls a network provider.
    """
    try:
        network = ipaddress.ip_network("100.64.0.0/10")
        candidate = ipaddress.ip_address(address)
        return candidate in network and interface.lower().startswith(("utun", "tailscale"))
    except (ValueError, AttributeError):
        return False


def device_endpoints(records=None):
    """Derive concrete Local and optional Tailscale/Remote PCServer routes."""
    records = host_interface_addresses() if records is None else records
    endpoints = []
    seen = set()
    for interface, address in records:
        if address in seen or not _usable_device_address(address):
            continue
        seen.add(address)
        if _tailnet_interface_address(interface, address):
            endpoints.append(DeviceEndpoint("Tailscale / Remote", address, "remote", interface))
        else:
            endpoints.append(DeviceEndpoint("Local network", address, "local", interface))
    return tuple(endpoints)


def preferred_local_address(addresses=None):
    """Choose the first concrete Local address, never the Remote tunnel route."""
    addresses = local_addresses() if addresses is None else addresses
    for value in addresses:
        if isinstance(value, DeviceEndpoint):
            if value.kind == "local" and _usable_device_address(value.address):
                return value.address
            continue
        _, address = value
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
