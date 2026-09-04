"""Non-secret desktop settings, validation, and per-user paths."""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import ipaddress
import json
import os
from pathlib import Path
import socket
import tempfile
import urllib.parse


APP_NAME = "PocketCinema"
SCHEMA_VERSION = 2
DEFAULT_STREMIO_SERVICE_URL = "http://127.0.0.1:11470"
DEFAULT_SERVER_PORT = 8755
DISCOVERY_PORT = 8754
OPEN_MEDIA_ADDON_PORT = 8756
LISTEN_MODES = ("automatic", "all_interfaces", "custom")
ADVERTISED_MODES = ("automatic", "manual")


class ConfigurationError(ValueError):
    """A user-editable desktop setting is invalid."""


@dataclass(frozen=True)
class DeviceEndpoint:
    """One concrete PCServer route derived from existing host interfaces."""

    label: str
    address: str
    kind: str = "local"
    interface: str = ""


@dataclass
class DesktopSettings:
    schema_version: int = SCHEMA_VERSION
    server_name: str = "PocketCinema Server"
    listen_mode: str = "automatic"
    listen_address: str = "127.0.0.1"
    listen_port: int = DEFAULT_SERVER_PORT
    advertised_mode: str = "automatic"
    advertised_address: str = "127.0.0.1"
    network_name: str = "Local"
    stremio_service_url: str = DEFAULT_STREMIO_SERVICE_URL
    ffmpeg_path: str = ""
    ffprobe_path: str = ""


def user_data_root(platform=None, environ=None):
    """Return the platform data root without creating or migrating anything."""
    platform = platform or os.sys.platform
    environ = environ or os.environ
    override = environ.get("POCKETCINEMA_DESKTOP_DATA_DIR")
    if override:
        return Path(override).expanduser()
    if platform.startswith("win"):
        return Path(environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / APP_NAME
    if platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    return Path(environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / APP_NAME


def settings_path(root):
    return Path(root) / "config.json"


def _valid_port(value, label):
    if isinstance(value, bool):
        raise ConfigurationError(f"{label} must be a port number")
    try:
        port = int(value)
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(f"{label} must be a port number") from exc
    if not 1 <= port <= 65535:
        raise ConfigurationError(f"{label} must be between 1 and 65535")
    return port


def _valid_bind_address(value):
    value = str(value).strip()
    if not value:
        raise ConfigurationError("Listen address is required")
    try:
        ipaddress.ip_address(value)
    except ValueError as exc:
        raise ConfigurationError("Listen address must be an IP address") from exc
    return value


def _valid_advertised_address(value):
    value = str(value).strip()
    if not value:
        raise ConfigurationError("Device-facing address is required")
    if value in {"0.0.0.0", "::"}:
        raise ConfigurationError("Device-facing address cannot be a wildcard")
    if any(char.isspace() for char in value) or "/" in value:
        raise ConfigurationError("Device-facing address must be a host or IP address")
    return value


def _valid_choice(value, values, label):
    value = str(value).strip()
    if value not in values:
        raise ConfigurationError(f"{label} is invalid")
    return value


def validate_stremio_service_url(value):
    value = str(value).strip()
    parsed = urllib.parse.urlsplit(value)
    if (
        parsed.scheme != "http"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise ConfigurationError(
            "Stremio Service endpoint must be an HTTP host and optional port"
        )
    try:
        port = parsed.port
    except ValueError as exc:
        raise ConfigurationError("Stremio Service endpoint has an invalid port") from exc
    if port is not None:
        _valid_port(port, "Stremio Service port")
    return urllib.parse.urlunsplit(("http", parsed.netloc, "", "", ""))


def _valid_tool_path(value, label):
    value = str(value or "").strip()
    if not value:
        return ""
    path = Path(value).expanduser()
    if not path.is_file():
        raise ConfigurationError(f"{label} path does not exist")
    if not os.access(path, os.X_OK):
        raise ConfigurationError(f"{label} path is not executable")
    return str(path.resolve())


def validate_settings(settings):
    if not isinstance(settings, DesktopSettings):
        settings = DesktopSettings(**settings)
    name = settings.server_name.strip()
    if not name or len(name) > 80 or any(char in name for char in "\r\n"):
        raise ConfigurationError("PCServer name must be 1-80 single-line characters")
    network_name = settings.network_name.strip()
    if not network_name or len(network_name) > 80 or any(char in network_name for char in "\r\n"):
        raise ConfigurationError("Network name must be 1-80 single-line characters")
    port = _valid_port(settings.listen_port, "Server port")
    if port in {DISCOVERY_PORT, OPEN_MEDIA_ADDON_PORT}:
        raise ConfigurationError("Server port conflicts with a PCServer helper port")
    return DesktopSettings(
        schema_version=SCHEMA_VERSION,
        server_name=name,
        listen_mode=_valid_choice(settings.listen_mode, LISTEN_MODES, "Listen mode"),
        listen_address=_valid_bind_address(settings.listen_address),
        listen_port=port,
        advertised_mode=_valid_choice(
            settings.advertised_mode, ADVERTISED_MODES, "PocketCinema address mode"
        ),
        advertised_address=_valid_advertised_address(settings.advertised_address),
        network_name=network_name,
        stremio_service_url=validate_stremio_service_url(settings.stremio_service_url),
        ffmpeg_path=_valid_tool_path(settings.ffmpeg_path, "FFmpeg"),
        ffprobe_path=_valid_tool_path(settings.ffprobe_path, "FFprobe"),
    )


def load_settings(root=None):
    root = Path(root or user_data_root())
    path = settings_path(root)
    if not path.exists():
        return DesktopSettings()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("settings must be an object")
        keys = set(DesktopSettings.__dataclass_fields__)
        values = {key: value for key, value in payload.items() if key in keys}
        # Version-1 preferences exposed explicit addresses. Retain that exact
        # behavior instead of silently replacing a working manual route.
        if "listen_mode" not in values:
            values["listen_mode"] = "custom"
        if "advertised_mode" not in values:
            values["advertised_mode"] = "manual"
        return validate_settings(values)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise ConfigurationError(f"Desktop settings could not be loaded: {exc}") from exc


def save_settings(settings, root=None):
    settings = validate_settings(settings)
    root = Path(root or user_data_root())
    root.mkdir(parents=True, exist_ok=True)
    path = settings_path(root)
    descriptor, temporary = tempfile.mkstemp(prefix="config-", suffix=".json", dir=root)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(asdict(settings), handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise
    return settings


def address_is_assigned(address):
    """Verify a concrete address remains bindable without hostname inference."""
    if address in {"0.0.0.0", "::"}:
        return True
    try:
        candidate = ipaddress.ip_address(address.split("%", 1)[0])
        family = socket.AF_INET6 if candidate.version == 6 else socket.AF_INET
        probe = socket.socket(family, socket.SOCK_STREAM)
        try:
            probe.bind((address, 0))
        finally:
            probe.close()
        return True
    except (OSError, ValueError):
        return False


def resolve_network_settings(settings, local_address):
    """Return the effective child configuration for the selected listen mode.

    Automatic choices are intentionally resolved at start/display time, while
    stored preferences remain non-secret choices rather than stale interface IPs.
    """
    settings = validate_settings(settings)
    local_address = str(local_address or "").strip()
    if settings.listen_mode == "automatic":
        if not local_address:
            raise ConfigurationError("No usable local network address was found")
        # Automatic is intentionally the simple direct-LAN choice. Remote
        # interfaces remain available through the explicit All interfaces mode.
        listen_address = local_address
        network_name = "Local network"
    elif settings.listen_mode == "all_interfaces":
        if not local_address:
            raise ConfigurationError("Choose a device-facing address in Advanced Settings")
        listen_address = "0.0.0.0"
        network_name = "All interfaces"
    else:
        listen_address = settings.listen_address
        network_name = settings.network_name

    advertised_address = (
        settings.advertised_address
        if settings.advertised_mode == "manual"
        else local_address or listen_address
    )
    if advertised_address in {"0.0.0.0", "::"}:
        raise ConfigurationError("Choose a device-facing address in Advanced Settings")
    return replace(
        settings,
        listen_address=listen_address,
        advertised_address=advertised_address,
        network_name=network_name,
    )


def derive_device_endpoints(settings, endpoints):
    """Choose the concrete Miyoo routes that this bind mode can actually serve.

    The bind socket and the routes a Miyoo can use are deliberately separate.
    A wildcard listener may serve more than one Local/Remote endpoint, while a
    specific listener must advertise only its matching address.  A manual
    advertised address remains an explicit compatibility override.
    """
    settings = validate_settings(settings)
    if settings.advertised_mode == "manual":
        return (DeviceEndpoint("Custom", settings.advertised_address, "manual"),)

    unique = []
    seen = set()
    for endpoint in endpoints:
        if not isinstance(endpoint, DeviceEndpoint):
            endpoint = DeviceEndpoint(*endpoint)
        if endpoint.address in seen or not _usable_detected_route(endpoint.address):
            continue
        seen.add(endpoint.address)
        unique.append(endpoint)

    if settings.listen_mode == "automatic":
        return tuple(endpoint for endpoint in unique if endpoint.kind == "local")
    if settings.listen_mode == "all_interfaces":
        return tuple(unique)
    custom_address = (
        settings.listen_address
        if settings.listen_address not in {"0.0.0.0", "::"}
        else settings.advertised_address
    )
    return (DeviceEndpoint("Custom", custom_address, "manual"),)


def _usable_detected_route(address):
    """Filter placeholder and non-device addresses from derived automatic routes."""
    try:
        _valid_advertised_address(address)
        candidate = ipaddress.ip_address(str(address).split("%", 1)[0])
    except (ConfigurationError, ValueError):
        return False
    return not (
        candidate.is_loopback
        or candidate.is_link_local
        or candidate.is_multicast
        or candidate.is_unspecified
    )


def pocketcinema_url(address, port):
    """Format a device-facing HTTP URL without exposing a wildcard bind."""
    address = str(address).strip()
    if ":" in address and not address.startswith("["):
        address = f"[{address}]"
    return f"http://{address}:{_valid_port(port, 'Server port')}"
