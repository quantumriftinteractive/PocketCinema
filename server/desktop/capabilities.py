"""Host capability discovery used by the desktop manager and tests."""
from dataclasses import dataclass
import ipaddress
import json
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
from .runtime import frozen, resource_path


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


def _usable_executable(path):
    return path.is_file() and os.access(path, os.X_OK)


def _stremio_runtime_tool(name, platform, environ):
    """Return the supported Windows Stremio-runtime tool when it is present.

    This preserves the existing Windows manager's lookup.  The executable is
    installed by Stremio; PocketCinema neither downloads nor redistributes it.
    """
    if not platform.startswith("win") or name not in {"ffmpeg", "ffprobe"}:
        return ""
    local_app_data = environ.get("LOCALAPPDATA", "").strip()
    if not local_app_data:
        return ""
    candidate = Path(local_app_data) / "Programs" / "LNV" / "Stremio-4" / f"{name}.exe"
    return str(candidate) if _usable_executable(candidate) else ""


def detect_tool(name, manual_path="", platform=None, environ=None):
    if manual_path:
        path = Path(manual_path).expanduser()
        available = _usable_executable(path)
        return ToolStatus(str(path), available, "manual")
    platform = platform or sys.platform
    if platform == "darwin" and frozen():
        bundled = resource_path("media-tools", "bin", name)
        if _usable_executable(bundled):
            return ToolStatus(str(bundled), True, "bundled")
    runtime_path = _stremio_runtime_tool(name, platform, environ or os.environ)
    if runtime_path:
        return ToolStatus(runtime_path, True, "Stremio runtime")
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


def _windows_interface_addresses(output):
    """Parse safe, active Windows interface records collected by PowerShell."""
    try:
        payload = json.loads(output) if output.strip() else []
    except (TypeError, json.JSONDecodeError):
        return []
    records = payload if isinstance(payload, list) else [payload]
    candidates = []
    for record in records:
        if not isinstance(record, dict):
            continue
        interface = record.get("interface")
        address = record.get("address")
        if not isinstance(interface, str) or not isinstance(address, str):
            continue
        if not _usable_device_address(address):
            continue
        # Retain the provider tunnel for accurate remote classification, but
        # do not advertise generic virtual/WSL adapters as a Miyoo LAN route.
        if _tailnet_interface_address(interface, address) or (
            not bool(record.get("virtual")) and bool(record.get("hardware"))
        ):
            candidates.append((interface, address))
    return candidates


def _read_windows_interface_addresses():
    command = (
        "$adapters = @{}; "
        "Get-NetAdapter -IncludeHidden -ErrorAction SilentlyContinue | "
        "ForEach-Object { $adapters[[string]$_.ifIndex] = $_ }; "
        "Get-NetIPAddress -AddressFamily IPv4,IPv6 -ErrorAction SilentlyContinue | "
        "Where-Object { $_.AddressState -eq 'Preferred' } | ForEach-Object { "
        "$ip = $_; $adapter = $adapters[[string]$ip.InterfaceIndex]; "
        "if ($adapter -and $adapter.Status -eq 'Up') { [PSCustomObject]@{ "
        "interface = $adapter.Name; address = $ip.IPAddress; "
        "virtual = [bool]$adapter.Virtual; hardware = [bool]$adapter.HardwareInterface "
        "} } } | ConvertTo-Json -Compress"
    )
    try:
        return subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        ).stdout
    except OSError:
        return ""


def host_interface_addresses(platform=None, ifconfig_output=None, windows_output=None):
    """Return usable host IP candidates with their OS interface identity."""
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
    elif platform.startswith("win"):
        if windows_output is None:
            windows_output = _read_windows_interface_addresses()
        records = _windows_interface_addresses(windows_output)
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
        candidate = ipaddress.ip_address(address)
        tunnel = interface.lower().startswith(("utun", "tailscale"))
        return tunnel and (
            candidate in ipaddress.ip_network("100.64.0.0/10")
            or candidate in ipaddress.ip_network("fd7a:115c:a1e0::/48")
        )
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
