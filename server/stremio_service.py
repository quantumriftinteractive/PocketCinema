import json
import re
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path


DEFAULT_TIMEOUT = 3
DEFAULT_STATUS_TTL = 10
LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}
WINDOWS_DRIVE_PATH = re.compile(r"^[A-Za-z]:[\\/]")


class StremioServiceError(RuntimeError):
    pass


def validate_service_base_url(value):
    """Validate the non-secret PCServer-to-Stremio-Service origin.

    This is deliberately independent of the Miyoo-facing bind address. The
    service can be local or on a separately reachable machine, but it is only
    ever contacted by PCServer.
    """
    if not value:
        return ""
    parsed = urllib.parse.urlparse(value)
    if (
        parsed.scheme != "http"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise ValueError("Stremio Service URL must be an HTTP origin without credentials or a path")
    try:
        parsed.port
    except ValueError as exc:
        raise ValueError("Stremio Service URL has an invalid port") from exc
    return value.rstrip("/")


# Kept as a source-compatible name for callers that imported the former helper.
validate_loopback_base_url = validate_service_base_url


def _file_url_path(value):
    if not isinstance(value, str) or not value.startswith("file://"):
        return None

    remainder = urllib.parse.unquote(value[len("file://") :])
    if WINDOWS_DRIVE_PATH.match(remainder):
        return Path(remainder)

    parsed = urllib.parse.urlparse(value)
    if parsed.netloc not in {"", "localhost"}:
        return None
    path = urllib.request.url2pathname(urllib.parse.unquote(parsed.path))
    return Path(path) if path else None


def resolve_allowed_path(path, allowed_roots):
    try:
        resolved = Path(path).resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    if not resolved.is_file():
        return None

    for root in allowed_roots:
        try:
            resolved.relative_to(root)
            return resolved
        except ValueError:
            continue
    return None


def resolve_allowed_file_url(value, allowed_roots):
    path = _file_url_path(value)
    return resolve_allowed_path(path, allowed_roots) if path is not None else None


def _manifest_supports_stream(manifest, item_type):
    resources = manifest.get("resources") or []
    resource_names = {
        item if isinstance(item, str) else item.get("name")
        for item in resources
    }
    return "stream" in resource_names and item_type in (manifest.get("types") or [])


class StremioServiceBackend:
    def __init__(
        self,
        base_url,
        allowed_roots,
        timeout=DEFAULT_TIMEOUT,
        status_ttl=DEFAULT_STATUS_TTL,
    ):
        self.base_url = validate_service_base_url(base_url)
        self.allowed_roots = tuple(
            Path(root).resolve() for root in allowed_roots if str(root).strip()
        )
        self.timeout = max(1, int(timeout))
        self.status_ttl = max(0, int(status_ttl))
        self._cached_status = None
        self._cached_at = 0
        self._lock = threading.Lock()

    @property
    def configured(self):
        return bool(self.base_url)

    def resolve_local_path(self, path):
        return resolve_allowed_path(path, self.allowed_roots)

    def _fetch_json(self, path):
        request = urllib.request.Request(
            self.base_url + path,
            headers={"User-Agent": "PocketCinema/1.0"},
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def status(self, force=False):
        if not self.configured:
            return {"configured": False, "reachable": False}

        now = time.monotonic()
        with self._lock:
            if (
                not force
                and self._cached_status is not None
                and now - self._cached_at < self.status_ttl
            ):
                return dict(self._cached_status)

        try:
            settings = self._fetch_json("/settings")
            manifest = self._fetch_json("/local-addon/manifest.json")
            values = settings.get("values") or {}
            status = {
                "configured": True,
                "reachable": True,
                "version": str(values.get("serverVersion") or ""),
                "local_addon_enabled": bool(values.get("localAddonEnabled")),
                "local_addon": {
                    "id": str(manifest.get("id") or ""),
                    "version": str(manifest.get("version") or ""),
                    "stream_capable": any(
                        _manifest_supports_stream(manifest, item_type)
                        for item_type in ("movie", "series")
                    ),
                },
            }
        except Exception as exc:
            status = {
                "configured": True,
                "reachable": False,
                "message": "Stremio Service is unavailable",
            }
            print(f"Stremio Service status failed: {exc}", flush=True)

        with self._lock:
            self._cached_status = dict(status)
            self._cached_at = now
        return status

    def resolve_streams(self, item_type, item_id):
        if not self.configured:
            return {"items": [], "message": ""}

        try:
            manifest = self._fetch_json("/local-addon/manifest.json")
            if not _manifest_supports_stream(manifest, item_type):
                return {
                    "items": [],
                    "message": "Stremio Service Local Files does not support this media type",
                }
            route = (
                "/local-addon/stream/"
                + urllib.parse.quote(item_type, safe="")
                + "/"
                + urllib.parse.quote(item_id, safe="")
                + ".json"
            )
            data = self._fetch_json(route)
        except Exception as exc:
            raise StremioServiceError("Stremio Service is unavailable") from exc

        raw_streams = data.get("streams") or []
        items = []
        for index, raw in enumerate(raw_streams):
            local_path = resolve_allowed_file_url(raw.get("url"), self.allowed_roots)
            if local_path is None:
                continue
            items.append(
                {
                    "name": raw.get("name") or raw.get("title") or f"Local file {index + 1}",
                    "description": raw.get("description") or "Stremio Service Local Files",
                    "local_path": str(local_path),
                }
            )

        if items:
            return {"items": items, "message": ""}
        if raw_streams:
            message = "Stremio Service returned no allowed direct local files"
        else:
            service_status = self.status()
            if service_status.get("reachable") and not service_status.get(
                "local_addon_enabled"
            ):
                message = "Stremio Service Local Files is disabled"
            else:
                message = "Stremio Service returned no matching local files"
        return {"items": [], "message": message}
