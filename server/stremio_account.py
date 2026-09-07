import base64
import binascii
import hashlib
import ipaddress
import json
import os
import threading
import time
import urllib.parse
import urllib.request
import zlib
from pathlib import Path


API_URL = "https://api.strem.io/api/addonCollectionGet"
DATASTORE_API_URL = "https://api.strem.io/api/datastoreGet"
DEFAULT_TIMEOUT = 15
DEFAULT_CACHE_TTL = 5 * 60
MAX_ADDONS = 128
MAX_WATCHED_BITFIELD_BYTES = 64 * 1024


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


def decode_watched_bitfield(value, ordered_video_ids):
    """Decode Stremio's anchored little-endian bitfield into watched IDs."""
    if not isinstance(value, str) or not value or not ordered_video_ids:
        return set()
    try:
        parts = value.split(":")
        if len(parts) < 3:
            return None
        encoded = parts.pop()
        anchor_length = int(parts.pop())
        anchor_id = ":".join(parts)
        if anchor_length < 1 or not anchor_id:
            return None
        anchor_index = ordered_video_ids.index(anchor_id)
        compressed = base64.b64decode(encoded, validate=True)
        values = zlib.decompress(compressed)
        if len(values) > MAX_WATCHED_BITFIELD_BYTES:
            return None
    except (ValueError, IndexError, TypeError, zlib.error, binascii.Error):
        return None

    offset = anchor_length - anchor_index - 1
    watched_ids = set()
    for index, video_id in enumerate(ordered_video_ids):
        previous_index = index + offset
        if previous_index < 0 or previous_index >= len(ordered_video_ids):
            continue
        byte_index = previous_index // 8
        bit_index = previous_index % 8
        if byte_index < len(values) and (values[byte_index] >> bit_index) & 1:
            watched_ids.add(video_id)
    return watched_ids


def resolve_episode_continuation(library_item, episodes):
    """Resolve one safe read-only continuation target from canonical episodes."""
    canonical = []
    seen_ids = set()
    seen_numbers = set()
    for episode in episodes or []:
        if not isinstance(episode, dict):
            return None
        video_id = episode.get("id")
        season = episode.get("season")
        number = episode.get("episode")
        if (
            not isinstance(video_id, str)
            or not video_id
            or isinstance(season, bool)
            or not isinstance(season, int)
            or season < 1
            or isinstance(number, bool)
            or not isinstance(number, int)
            or number < 1
            or video_id in seen_ids
            or (season, number) in seen_numbers
        ):
            return None
        seen_ids.add(video_id)
        seen_numbers.add((season, number))
        canonical.append(episode)

    if not canonical:
        return None

    state = library_item if isinstance(library_item, dict) else {}
    ordered_video_ids = [episode["id"] for episode in canonical]
    watched_ids = decode_watched_bitfield(state.get("_watched"), ordered_video_ids)
    if watched_ids is None:
        return None

    current_id = state.get("video_id")
    current_index = (
        ordered_video_ids.index(current_id)
        if isinstance(current_id, str) and current_id in ordered_video_ids
        else -1
    )
    if current_index >= 0:
        if current_id not in watched_ids:
            target = canonical[current_index]
            kind = "continue"
        elif current_index + 1 < len(canonical):
            target = canonical[current_index + 1]
            kind = "next"
        else:
            return None
    else:
        watched_indices = [
            index for index, video_id in enumerate(ordered_video_ids)
            if video_id in watched_ids
        ]
        if not watched_indices or watched_indices[-1] + 1 >= len(canonical):
            return None
        target = canonical[watched_indices[-1] + 1]
        kind = "next"

    return {
        "kind": kind,
        "id": target["id"],
        "title": target.get("title") or "Episode %d" % target["episode"],
        "year": target.get("year"),
        "season": target["season"],
        "episode": target["episode"],
    }


def normalize_episode_state(library_item, episodes):
    """Return safe watched/current flags aligned to normalized episode metadata."""
    normalized_episodes = [
        episode
        for episode in episodes or []
        if isinstance(episode, dict) and isinstance(episode.get("id"), str)
    ]
    ordered_video_ids = [episode["id"] for episode in normalized_episodes]
    state = library_item if isinstance(library_item, dict) else {}
    current_id = state.get("video_id") or ""
    if current_id not in ordered_video_ids:
        current_id = ""

    decoded = decode_watched_bitfield(state.get("_watched"), ordered_video_ids)
    watched_ids = decoded if isinstance(decoded, set) else set()

    episode_state = {
        video_id: {
            "watched": video_id in watched_ids,
            "current": video_id == current_id,
        }
        for video_id in ordered_video_ids
    }
    season_video_ids = {}
    for episode in normalized_episodes:
        season = episode.get("season")
        if isinstance(season, bool) or season in (None, ""):
            continue
        season_video_ids.setdefault(str(season), []).append(episode["id"])

    normalized_state = {
        "current_id": current_id,
        "episodes": episode_state,
        "seasons": {
            season: {
                "watched": bool(video_ids)
                and all(episode_state[video_id]["watched"] for video_id in video_ids),
            }
            for season, video_ids in season_video_ids.items()
        },
    }
    continuation = resolve_episode_continuation(library_item, normalized_episodes)
    if continuation is not None:
        normalized_state["continuation"] = continuation
    return normalized_state


def resource_url(transport_url, resource, item_type, item_id, extra=None):
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
    )
    if extra:
        values = {
            str(key): str(value)
            for key, value in extra.items()
            if value not in (None, "", 0)
        }
        if values:
            path += "/" + urllib.parse.urlencode(values)
    path += ".json"
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
        self._library_cache = None
        self._library_cache_at = 0
        self._library_auth_fingerprint = ""
        self._library_last_error = ""
        self._lock = threading.Lock()

    def _read_auth_key(self):
        env_key = os.environ.get("POCKETCINEMA_STREMIO_AUTH_KEY", "").strip()
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

    def _post_json(self, payload, api_url=None):
        request = urllib.request.Request(
            api_url or self.api_url,
            data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "User-Agent": "PocketCinema/0.11",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def _fetch_json(self, url):
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "PocketCinema/0.11"},
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

    @staticmethod
    def _milliseconds_to_seconds(value):
        try:
            return max(0, int(float(value or 0) / 1000))
        except (TypeError, ValueError):
            return 0

    def _normalize_library_item(self, raw):
        if not isinstance(raw, dict):
            return None
        if raw.get("removed") or raw.get("temp"):
            return None

        item_type = raw.get("type")
        if item_type not in {"movie", "series"}:
            return None
        item_id = _safe_text(raw.get("_id") or raw.get("id"), "", 160)
        title = _safe_text(raw.get("name"), item_id, 240)
        if not item_id or not title:
            return None

        state = raw.get("state")
        if not isinstance(state, dict):
            state = {}
        video_id = _safe_text(state.get("video_id"), "", 160)
        last_watched = state.get("lastWatched")
        if isinstance(last_watched, bool):
            last_watched = None
        elif isinstance(last_watched, (int, float)):
            last_watched = max(0, last_watched)
        elif not isinstance(last_watched, str):
            last_watched = None
        else:
            last_watched = _safe_text(last_watched, "", 64) or None

        try:
            times_watched = max(0, int(float(state.get("timesWatched") or 0)))
        except (TypeError, ValueError):
            times_watched = 0

        return {
            "id": item_id,
            "type": item_type,
            "title": title,
            "poster": (
                raw.get("poster")
                if isinstance(raw.get("poster"), str)
                and validate_direct_stream_url(raw.get("poster"))
                else ""
            ),
            "watched": item_type == "movie" and times_watched > 0,
            "last_watched": last_watched,
            "position_seconds": self._milliseconds_to_seconds(
                state.get("timeOffset")
            ),
            "duration_seconds": self._milliseconds_to_seconds(
                state.get("duration")
            ),
            "video_id": video_id,
            "current": item_type == "series" and bool(video_id),
            "_mtime": raw.get("_mtime"),
            "_watched": _safe_text(state.get("watched"), "", 8192),
        }

    def _load_library(self, auth_key):
        try:
            payload = self._post_json(
                {
                    "authKey": auth_key,
                    "collection": "libraryItem",
                    "ids": [],
                    "all": True,
                },
                api_url=DATASTORE_API_URL,
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
        if not isinstance(result, list):
            raise StremioAccountError("Stremio account library response is invalid")

        items = []
        seen = set()
        for raw in result:
            item = self._normalize_library_item(raw)
            if item is None or (item["type"], item["id"]) in seen:
                continue
            seen.add((item["type"], item["id"]))
            items.append(item)
        return items

    def library(self, force=False):
        auth_key = self._read_auth_key()
        if not auth_key:
            with self._lock:
                self._library_cache = None
                self._library_auth_fingerprint = ""
                self._library_last_error = ""
            return []

        fingerprint = hashlib.sha256(auth_key.encode("utf-8")).hexdigest()
        now = time.monotonic()
        with self._lock:
            if (
                not force
                and self._library_cache is not None
                and fingerprint == self._library_auth_fingerprint
                and now - self._library_cache_at < self.cache_ttl
            ):
                return [dict(item) for item in self._library_cache]

        try:
            items = self._load_library(auth_key)
        except StremioAccountError as exc:
            with self._lock:
                self._library_last_error = str(exc)
            raise
        with self._lock:
            self._library_cache = list(items)
            self._library_cache_at = now
            self._library_auth_fingerprint = fingerprint
            self._library_last_error = ""
        return [dict(item) for item in items]

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
            checked = (
                self._cache is not None
                or self._library_cache is not None
                or bool(last_error)
            )
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

    def fetch_subtitles(self, source, item_type, item_id, extra=None):
        try:
            url = resource_url(
                source["transport_url"],
                "subtitles",
                item_type,
                item_id,
                extra,
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
