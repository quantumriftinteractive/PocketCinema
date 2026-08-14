import hashlib
import ipaddress
import json
import os
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path


API_URL = "https://api.strem.io/api/addonCollectionGet"
DEFAULT_TIMEOUT = 15
DEFAULT_CACHE_TTL = 5 * 60
MAX_ADDONS = 128
class StremioAccountError(RuntimeError):
    pass


def _safe_text(value, fallback, maximum):
    text = str(value or "").strip()
    if any(marker in text.lower() for marker in ("http://", "https://", "file://")):
        return fallback
    return text[:maximum] or fallback


def _resource_names(manifest):
    resources = manifest.get("resources") or []
    return sorted(
        {
            item if isinstance(item, str) else item.get("name")
            for item in resources
            if isinstance(item, (str, dict))
        }
        - {None}
    )


def manifest_supports(manifest, resource, item_type):
    return resource in _resource_names(manifest) and item_type in (
        manifest.get("types") or []
    )


def validate_transport_url(value):
    try:
        parsed = urllib.parse.urlparse(value)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or not parsed.path.endswith("/manifest.json")
        ):
            return False
        hostname = parsed.hostname.lower()
        if hostname == "localhost" or hostname.endswith((".localhost", ".local")):
            return False
        try:
            return ipaddress.ip_address(hostname).is_global
        except ValueError:
            return True
    except (TypeError, ValueError):
        return False


def validate_direct_stream_url(value):
    try:
        parsed = urllib.parse.urlparse(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.fragment
        ):
            return False
        hostname = parsed.hostname.lower()
        if hostname == "localhost" or hostname.endswith((".localhost", ".local")):
            return False
        try:
            return ipaddress.ip_address(hostname).is_global
        except ValueError:
            return True
    except (TypeError, ValueError):
        return False


def has_unsupported_stream_shape(raw):
    if not isinstance(raw, dict):
        return True
    return any(raw.get(key) for key in ("infoHash", "externalUrl", "ytId"))


def resource_url(transport_url, resource, item_type, item_id):
    parsed = urllib.parse.urlparse(transport_url)
    base_path = parsed.path[: -len("/manifest.json")]
    path = (
        base_path
        + "/"
        + urllib.parse.quote(resource, safe="")
        + "/"
        + urllib.parse.quote(item_type, safe="")
        + "/"
        + urllib.parse.quote(item_id, safe="")
        + ".json"
    )
    return urllib.parse.urlunparse(
        (parsed.scheme, parsed.netloc, path, "", "", "")
    )


class StremioAccountBackend:
    def __init__(
        self,
        config_path,
        timeout=DEFAULT_TIMEOUT,
        cache_ttl=DEFAULT_CACHE_TTL,
        api_url=API_URL,
    ):
        self.config_path = Path(config_path)
        self.timeout = max(1, int(timeout))
        self.cache_ttl = max(0, int(cache_ttl))
        self.api_url = api_url
        self._cache = None
        self._cache_at = 0
        self._auth_fingerprint = ""
        self._last_error = ""
        self._lock = threading.Lock()

    def _read_auth_key(self):
        env_key = os.environ.get("POCKETSTREMIO_STREMIO_AUTH_KEY", "").strip()
        if env_key:
            return env_key
        try:
            data = json.loads(self.config_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return ""
        except (OSError, json.JSONDecodeError) as exc:
            raise StremioAccountError("Stremio account configuration is invalid") from exc
        auth_key = data.get("auth_key")
        if not isinstance(auth_key, str) or not auth_key.strip():
            raise StremioAccountError("Stremio account configuration is invalid")
        return auth_key.strip()

    def _post_json(self, payload):
        request = urllib.request.Request(
            self.api_url,
            data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "User-Agent": "PocketStremio/0.11",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def _fetch_json(self, url):
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "PocketStremio/0.11"},
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def _normalize_descriptor(self, raw):
        if not isinstance(raw, dict):
            return None
        manifest = raw.get("manifest")
        transport_url = raw.get("transportUrl")
        if not isinstance(manifest, dict) or not isinstance(transport_url, str):
            return None

        behavior_hints = manifest.get("behaviorHints") or {}
        p2p = bool(behavior_hints.get("p2p"))
        transport_supported = validate_transport_url(transport_url)
        if p2p:
            message = "P2P addon is unsupported"
        elif not transport_supported:
            message = "Addon transport is unsupported"
        else:
            message = ""
        flags = raw.get("flags") or {}
        resources = _resource_names(manifest)
        types = sorted(
            item for item in (manifest.get("types") or []) if isinstance(item, str)
        )
        return {
            "key": hashlib.sha256(transport_url.encode("utf-8")).hexdigest()[:12],
            "id": _safe_text(manifest.get("id"), "", 160),
            "name": _safe_text(manifest.get("name"), "Unnamed addon", 160),
            "version": _safe_text(manifest.get("version"), "", 80),
            "types": types,
            "resources": resources,
            "official": bool(flags.get("official")),
            "protected": bool(flags.get("protected")),
            "stream_capable": "stream" in resources,
            "usable": transport_supported and not p2p,
            "message": message,
            "transport_url": transport_url,
            "manifest": manifest,
        }

    def _load_collection(self, auth_key):
        try:
            payload = self._post_json(
                {
                    "type": "AddonCollectionGet",
                    "authKey": auth_key,
                    "update": True,
                }
            )
        except Exception as exc:
            raise StremioAccountError("Stremio account service is unavailable") from exc
        if not isinstance(payload, dict):
            raise StremioAccountError("Stremio account response is invalid")
        if "error" in payload:
            code = (payload.get("error") or {}).get("code")
            if code == 1:
                raise StremioAccountError("Stremio account session expired")
            raise StremioAccountError("Stremio account request was rejected")
        result = payload.get("result")
        if not isinstance(result, dict) or not isinstance(result.get("addons"), list):
            raise StremioAccountError("Stremio account response is invalid")

        addons = []
        for raw in result["addons"][:MAX_ADDONS]:
            addon = self._normalize_descriptor(raw)
            if addon is not None:
                addons.append(addon)
        return addons

    def collection(self, force=False):
        auth_key = self._read_auth_key()
        if not auth_key:
            with self._lock:
                self._cache = None
                self._auth_fingerprint = ""
                self._last_error = ""
            return []

        fingerprint = hashlib.sha256(auth_key.encode("utf-8")).hexdigest()
        now = time.monotonic()
        with self._lock:
            if (
                not force
                and self._cache is not None
                and fingerprint == self._auth_fingerprint
                and now - self._cache_at < self.cache_ttl
            ):
                return list(self._cache)

        try:
            addons = self._load_collection(auth_key)
        except StremioAccountError as exc:
            with self._lock:
                self._last_error = str(exc)
            raise
        with self._lock:
            self._cache = list(addons)
            self._cache_at = now
            self._auth_fingerprint = fingerprint
            self._last_error = ""
        return addons

    def status(self):
        try:
            configured = bool(self._read_auth_key())
            config_error = ""
        except StremioAccountError as exc:
            configured = True
            config_error = str(exc)
        with self._lock:
            addons = list(self._cache or [])
            last_error = config_error or self._last_error
            checked = self._cache is not None or bool(last_error)
        return {
            "configured": configured,
            "checked": checked,
            "authenticated": configured and checked and not bool(last_error),
            "addons": len(addons),
            "stream_addons": sum(
                1 for addon in addons if addon["usable"] and addon["stream_capable"]
            ),
            "message": last_error,
        }

    def public_collection(self, force=False):
        addons = self.collection(force=force)
        configured = bool(self._read_auth_key())
        items = [
            {
                key: value
                for key, value in addon.items()
                if key not in {"key", "transport_url", "manifest"}
            }
            for addon in addons
        ]
        return {
            "configured": configured,
            "authenticated": configured,
            "count": len(items),
            "stream_addons": sum(
                1 for item in items if item["usable"] and item["stream_capable"]
            ),
            "items": items,
        }

    def stream_sources(self, item_type):
        return [
            addon
            for addon in self.collection()
            if addon["usable"]
            and manifest_supports(addon["manifest"], "stream", item_type)
        ]

    def subtitle_sources(self, item_type):
        return [
            addon
            for addon in self.collection()
            if addon["usable"]
            and manifest_supports(addon["manifest"], "subtitles", item_type)
        ]

    def catalog_sources(self, item_type):
        catalogs = []
        for source in self.collection():
            manifest = source["manifest"]
            if (
                not source["usable"]
                or not manifest_supports(manifest, "catalog", item_type)
                or not manifest_supports(manifest, "stream", item_type)
            ):
                continue
            for raw in manifest.get("catalogs") or []:
                if not isinstance(raw, dict) or raw.get("type") != item_type:
                    continue
                catalog_id = raw.get("id")
                if not isinstance(catalog_id, str) or not catalog_id.strip():
                    continue
                catalogs.append(
                    {
                        "source": source,
                        "id": catalog_id.strip()[:160],
                        "name": _safe_text(raw.get("name"), source["name"], 160),
                    }
                )
        return catalogs

    def fetch_catalog(self, source, item_type, catalog_id):
        try:
            url = resource_url(
                source["transport_url"], "catalog", item_type, catalog_id
            )
            payload = self._fetch_json(url)
        except Exception as exc:
            raise StremioAccountError(
                f"{source['name']} is unavailable"
            ) from exc
        if not isinstance(payload, dict) or not isinstance(
            payload.get("metas", []), list
        ):
            raise StremioAccountError(f"{source['name']} returned an invalid response")
        return payload.get("metas") or []

    def fetch_streams(self, source, item_type, item_id):
        try:
            url = resource_url(
                source["transport_url"], "stream", item_type, item_id
            )
            payload = self._fetch_json(url)
        except Exception as exc:
            raise StremioAccountError(
                f"{source['name']} is unavailable"
            ) from exc
        if not isinstance(payload, dict) or not isinstance(
            payload.get("streams", []), list
        ):
            raise StremioAccountError(f"{source['name']} returned an invalid response")
        return payload.get("streams") or []

    def fetch_subtitles(self, source, item_type, item_id):
        try:
            url = resource_url(
                source["transport_url"], "subtitles", item_type, item_id
            )
            payload = self._fetch_json(url)
        except Exception as exc:
            raise StremioAccountError(
                f"{source['name']} is unavailable"
            ) from exc
        if not isinstance(payload, dict) or not isinstance(
            payload.get("subtitles", []), list
        ):
            raise StremioAccountError(f"{source['name']} returned an invalid response")
        return payload.get("subtitles") or []
