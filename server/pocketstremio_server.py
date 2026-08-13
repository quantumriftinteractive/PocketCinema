#!/usr/bin/env python3
import argparse
import hashlib
import json
import mimetypes
import os
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

try:
    from server import open_media_addon
    from server import playback_compatibility
except ImportError:
    import open_media_addon
    import playback_compatibility


CINEMETA_BASE = "https://v3-cinemeta.strem.io"
SERVER_VERSION = "0.9-real-series-poc"
DEFAULT_TIMEOUT = 15
MEDIA_TIMEOUT = 30
BIG_BUCK_BUNNY_ID = "tt1254207"
TEST_SERIES_ID = "pocketstremio-test-series"
MAX_CONTINUE_ITEMS = 50
DEFAULT_SESSION_TTL = 6 * 60 * 60
DEFAULT_MAX_SESSIONS = 128
DEFAULT_PROBE_CACHE_TTL = 7 * 24 * 60 * 60
DEFAULT_MAX_PROBE_CACHE = 256
COMPATIBILITY_FIXTURES = (
    {
        "filename": "test-video.mp4",
        "name": "PocketStremio hosted test video",
        "description": "H.264 High/AAC MP4 | 640x360 | 30 fps | 1.58 Mb/s",
        "duration_seconds": 6,
        "compatibility": {
            "status": "confirmed",
            "message": "Confirmed H.264/AAC 640x360 regression fixture",
        },
        "required": True,
    },
    {
        "filename": "compat-vp8-vorbis.webm",
        "name": "Compatibility test - VP8/Vorbis WebM",
        "description": "VP8/Vorbis WebM | 640x360 | 30 fps | local fixture",
        "duration_seconds": 6,
        "compatibility": {
            "status": "confirmed",
            "message": "Confirmed VP8/Vorbis 640x360 regression fixture",
        },
    },
    {
        "filename": "compat-h264-opus.mkv",
        "name": "Compatibility rejection - H.264/Opus Matroska",
        "description": "Expected rejection: this FFplay build lacks Opus audio",
        "duration_seconds": 6,
        "compatibility": {
            "status": "candidate",
            "message": "Server preflight must inspect the audio codec",
        },
    },
)
SERIES_PLAYBACK_FIXTURE = {
    "filename": "series-av-sync.mp4",
    "name": "Offline episode A/V sync test",
    "description": "30-second H.264/AAC fixture with matching flashes and beeps",
    "duration_seconds": 30,
    "compatibility": {
        "status": "confirmed",
        "message": "Confirmed H.264/AAC 640x360 profile",
    },
}
COMPATIBILITY_FIXTURE_NAMES = {
    fixture["filename"] for fixture in COMPATIBILITY_FIXTURES
} | {SERIES_PLAYBACK_FIXTURE["filename"]}
TEST_SERIES_META = {
    "id": TEST_SERIES_ID,
    "type": "series",
    "name": "PocketStremio Test Series",
    "releaseInfo": "2026",
    "description": "Deterministic offline fixture for season and episode browsing.",
    "videos": [
        {
            "id": f"{TEST_SERIES_ID}:1:1",
            "season": 1,
            "episode": 1,
            "name": "First Contact",
            "released": "2026-01-01",
            "overview": "Tests selection of the first episode.",
        },
        {
            "id": f"{TEST_SERIES_ID}:1:2",
            "season": 1,
            "episode": 2,
            "name": "The Proxy Path",
            "released": "2026-01-08",
            "overview": "Tests episode identity through a configured network path.",
        },
        {
            "id": f"{TEST_SERIES_ID}:1:3",
            "season": 1,
            "episode": 3,
            "name": "Playback Ready",
            "released": "2026-01-15",
            "overview": "Tests the existing playback handoff.",
        },
        {
            "id": f"{TEST_SERIES_ID}:2:1",
            "season": 2,
            "episode": 1,
            "name": "Return to OnionOS",
            "released": "2026-02-01",
            "overview": "Tests navigation into a second season.",
        },
        {
            "id": f"{TEST_SERIES_ID}:2:2",
            "season": 2,
            "episode": 2,
            "name": "The Final Range",
            "released": "2026-02-08",
            "overview": "Tests byte-range playback for another episode ID.",
        },
    ],
}
TEST_SERIES_EPISODES = {
    video["id"]: video for video in TEST_SERIES_META["videos"]
}


def fetch_json(url, timeout=DEFAULT_TIMEOUT):
    req = urllib.request.Request(url, headers={"User-Agent": "PocketStremio/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def load_stream_addons(config_path, stremio_service_url):
    addons = []
    if stremio_service_url:
        addons.append(
            {
                "name": "Stremio Service local addon",
                "manifest_url": stremio_service_url.rstrip("/") + "/local-addon/manifest.json",
            }
        )

    raw = os.environ.get("POCKETSTREMIO_STREAM_ADDONS", "").strip()
    if raw:
        addons.extend(
            {"name": "env addon", "manifest_url": item.strip()}
            for item in raw.split(",")
            if item.strip()
        )
        return addons

    path = Path(config_path)
    if not path.is_file():
        return addons

    data = json.loads(path.read_text(encoding="utf-8"))
    addons.extend(
        {"name": item.get("name", "configured addon"), "manifest_url": item["manifest_url"]}
        for item in data.get("addons", [])
        if item.get("enabled", True)
    )
    return addons


def addon_base_from_manifest(manifest_url):
    parsed = urllib.parse.urlparse(manifest_url)
    if parsed.path.endswith("/manifest.json"):
        path = parsed.path[: -len("/manifest.json")]
    else:
        path = parsed.path.rstrip("/")
    return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))


def nonnegative_int(value):
    try:
        return max(0, int(float(value or 0)))
    except (TypeError, ValueError):
        return 0


def release_year(value):
    release = str(value or "")
    for token in release.replace("-", " ").split():
        if len(token) >= 4 and token[:4].isdigit():
            return int(token[:4])
    return None


def normalize_meta(meta):
    release = str(meta.get("releaseInfo") or meta.get("year") or "")
    item_type = meta.get("type") or "movie"
    normalized = {
        "id": meta.get("id") or meta.get("imdb_id"),
        "imdb_id": meta.get("imdb_id") or meta.get("id"),
        "type": item_type,
        "title": meta.get("name") or meta.get("title") or "",
        "year": release_year(release),
        "poster": meta.get("poster") or "",
        "description": meta.get("description") or "",
    }
    if item_type != "series" or "videos" not in meta:
        return normalized

    episodes = []
    season_counts = {}
    for video in meta.get("videos") or []:
        video_id = str(video.get("id") or "")
        season = nonnegative_int(video.get("season"))
        episode = nonnegative_int(video.get("episode"))
        if not video_id or season < 1 or episode < 1:
            continue
        episodes.append(
            {
                "id": video_id,
                "title": video.get("name") or video.get("title") or f"Episode {episode}",
                "season": season,
                "episode": episode,
                "year": release_year(video.get("released")) or normalized["year"],
                "released": video.get("released") or "",
                "description": video.get("overview") or video.get("description") or "",
            }
        )
        season_counts[season] = season_counts.get(season, 0) + 1

    episodes.sort(key=lambda item: (item["season"], item["episode"]))
    normalized["seasons"] = [
        {"number": season, "episode_count": season_counts[season]}
        for season in sorted(season_counts)
    ]
    normalized["episodes"] = episodes
    return normalized


def split_episode_video_id(item_id):
    parts = str(item_id or "").rsplit(":", 2)
    if len(parts) != 3 or not parts[0]:
        return None
    season = nonnegative_int(parts[1])
    episode = nonnegative_int(parts[2])
    if season < 1 or episode < 1:
        return None
    return parts[0], season, episode


def normalize_series_episode(meta, item_id):
    parsed = split_episode_video_id(item_id)
    if not parsed:
        return None
    series_id, season, episode_number = parsed
    series = normalize_meta(meta)
    episode = next(
        (item for item in series.get("episodes", []) if item["id"] == item_id),
        None,
    )
    if not episode:
        return None
    return {
        "id": item_id,
        "imdb_id": "",
        "type": "series",
        "title": episode["title"],
        "year": episode["year"],
        "poster": series.get("poster") or "",
        "description": episode.get("description") or series.get("description") or "",
        "series_id": series_id,
        "series_title": series.get("title") or "",
        "season": season,
        "episode": episode_number,
        "released": episode.get("released") or "",
    }


def normalize_test_episode(item_id):
    video = TEST_SERIES_EPISODES.get(item_id)
    if not video:
        return None
    season = nonnegative_int(video["season"])
    episode = nonnegative_int(video["episode"])
    return {
        "id": item_id,
        "imdb_id": "",
        "type": "series",
        "title": f"PocketStremio Test Series S{season}E{episode}: {video['name']}",
        "year": release_year(video.get("released")),
        "poster": "",
        "description": video.get("overview") or "",
        "series_id": TEST_SERIES_ID,
        "series_title": TEST_SERIES_META["name"],
        "season": season,
        "episode": episode,
    }


def stream_label(stream, fallback):
    name = stream.get("name") or stream.get("title") or fallback
    description = stream.get("description") or ""
    if description:
        return f"{name} - {description[:80]}"
    return name


def manifest_supports(manifest, resource, item_type):
    resources = manifest.get("resources") or []
    resource_names = {
        item.get("name") if isinstance(item, dict) else item
        for item in resources
    }
    types = manifest.get("types") or []
    return resource in resource_names and (not types or item_type in types)


class SessionStore:
    def __init__(self, ttl_seconds=DEFAULT_SESSION_TTL, max_items=DEFAULT_MAX_SESSIONS):
        self.ttl_seconds = max(1, int(ttl_seconds))
        self.max_items = max(1, int(max_items))
        self.items = {}
        self.lock = threading.Lock()

    def _remove_expired(self, now):
        expired = [
            session_id
            for session_id, item in self.items.items()
            if now - item.get("created_at", 0) >= self.ttl_seconds
        ]
        for session_id in expired:
            self.items.pop(session_id, None)

    def create(self, item):
        now = time.time()
        with self.lock:
            self._remove_expired(now)
            while len(self.items) >= self.max_items:
                oldest = min(self.items, key=lambda key: self.items[key].get("created_at", 0))
                self.items.pop(oldest, None)
            session_id = secrets.token_hex(8)
            self.items[session_id] = {"created_at": now, **item}
            return session_id

    def get(self, session_id):
        now = time.time()
        with self.lock:
            item = self.items.get(session_id)
            if not item:
                return None, False
            if now - item.get("created_at", 0) >= self.ttl_seconds:
                self.items.pop(session_id, None)
                return None, True
            return dict(item), False

    def __len__(self):
        with self.lock:
            self._remove_expired(time.time())
            return len(self.items)


class ProbeCache:
    def __init__(
        self,
        path,
        ttl_seconds=DEFAULT_PROBE_CACHE_TTL,
        max_items=DEFAULT_MAX_PROBE_CACHE,
    ):
        self.path = Path(path)
        self.ttl_seconds = max(1, int(ttl_seconds))
        self.max_items = max(1, int(max_items))
        self.lock = threading.Lock()
        self.items = self._load()

    @staticmethod
    def key(url):
        return hashlib.sha256(url.encode()).hexdigest()

    def _load(self):
        if not self.path.is_file():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        temp_path.write_text(
            json.dumps(self.items, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        os.replace(temp_path, self.path)

    def _prune(self, now):
        expired = [
            key
            for key, item in self.items.items()
            if not isinstance(item, dict)
            or now - item.get("updated_at", 0) >= self.ttl_seconds
        ]
        for key in expired:
            self.items.pop(key, None)

        overflow = len(self.items) - self.max_items
        if overflow > 0:
            oldest = sorted(
                self.items,
                key=lambda key: self.items[key].get("updated_at", 0),
            )[:overflow]
            for key in oldest:
                self.items.pop(key, None)
        return bool(expired or overflow > 0)

    def get(self, url):
        cache_key = self.key(url)
        with self.lock:
            changed = self._prune(time.time())
            item = self.items.get(cache_key)
            if changed:
                self._save()
            if not item:
                return None
            return dict(item.get("compatibility") or {}) or None

    def set(self, url, compatibility):
        cache_key = self.key(url)
        with self.lock:
            self.items[cache_key] = {
                "updated_at": int(time.time()),
                "compatibility": compatibility,
            }
            self._prune(time.time())
            self._save()

    def __len__(self):
        with self.lock:
            if self._prune(time.time()):
                self._save()
            return len(self.items)


class ProgressStore:
    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.Lock()
        self.items = self._load()

    @staticmethod
    def key(item_type, item_id):
        return f"{item_type}:{item_id}"

    def _load(self):
        if not self.path.is_file():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        temp_path.write_text(
            json.dumps(self.items, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        os.replace(temp_path, self.path)

    def list_items(self):
        with self.lock:
            return sorted(
                (dict(item) for item in self.items.values()),
                key=lambda item: item.get("updated_at", 0),
                reverse=True,
            )[:MAX_CONTINUE_ITEMS]

    def update(self, payload):
        item_type = str(payload.get("type") or "").strip()[:32]
        item_id = str(payload.get("id") or "").strip()[:160]
        title = str(payload.get("title") or "").strip()[:240]
        if not item_type or not item_id or not title:
            raise ValueError("type, id, and title are required")

        try:
            position = max(0, int(float(payload.get("position_seconds") or 0)))
            duration = max(0, int(float(payload.get("duration_seconds") or 0)))
            year = int(payload["year"]) if str(payload.get("year") or "").isdigit() else None
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid progress value") from exc

        completed_value = payload.get("completed")
        completed = completed_value is True or str(completed_value).lower() == "true"
        if duration and position >= max(duration - 30, duration * 0.9):
            completed = True

        key = self.key(item_type, item_id)
        with self.lock:
            if completed:
                self.items.pop(key, None)
                self._save()
                return None

            item = {
                "type": item_type,
                "id": item_id,
                "title": title,
                "year": year,
                "position_seconds": position,
                "duration_seconds": duration,
                "updated_at": int(time.time()),
            }
            self.items[key] = item
            if len(self.items) > MAX_CONTINUE_ITEMS:
                oldest = min(self.items, key=lambda item_key: self.items[item_key].get("updated_at", 0))
                self.items.pop(oldest, None)
            self._save()
            return dict(item)


class PocketStremioHandler(BaseHTTPRequestHandler):
    server_version = "PocketStremio/0.9"

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        parts = [
            urllib.parse.unquote(part) for part in parsed.path.split("/") if part
        ]

        if parsed.path == "/api/status":
            session_count = len(self.server.play_sessions)
            probe_count = len(self.server.probe_cache)
            progress_count = len(self.server.progress_store.list_items())
            self.write_json(
                {
                    "status": "ok",
                    "service": "pocketstremio-server",
                    "version": SERVER_VERSION,
                    "message": "PocketStremio server is reachable",
                    "uptime_seconds": max(
                        0, int(time.time() - self.server.started_at)
                    ),
                    "stream_addons": len(self.server.stream_addons),
                    "continue_watching": progress_count,
                    "play_sessions": session_count,
                    "media_preflight": bool(self.server.ffprobe_path),
                    "probe_cache": probe_count,
                    "sessions": {
                        "active": session_count,
                        "maximum": self.server.play_sessions.max_items,
                        "ttl_seconds": self.server.play_sessions.ttl_seconds,
                    },
                    "cache": {
                        "entries": probe_count,
                        "maximum": self.server.probe_cache.max_items,
                        "ttl_seconds": self.server.probe_cache.ttl_seconds,
                    },
                    "state": {
                        "progress_items": progress_count,
                        "play_sessions_persistent": False,
                        "probe_cache_persistent": True,
                    },
                }
            )
            return

        if parsed.path == "/api/search":
            self.handle_search(parsed)
            return

        if len(parts) == 4 and parts[:2] == ["api", "meta"]:
            self.handle_meta(parts[2], parts[3])
            return

        if len(parts) == 4 and parts[:2] == ["api", "streams"]:
            self.handle_streams(parts[2], parts[3])
            return

        if len(parts) == 4 and parts[:2] == ["api", "subtitles"]:
            self.handle_subtitles(parts[2], parts[3], parsed)
            return

        if parsed.path == "/api/continue-watching":
            items = self.server.progress_store.list_items()
            self.write_json({"count": len(items), "items": items})
            return

        if len(parts) == 2 and parts[0] == "play":
            self.handle_play_session(parts[1])
            return

        if len(parts) == 2 and parts[0] == "subtitle":
            self.handle_subtitle(parts[1])
            return

        if parsed.path == "/media/test-video.mp4":
            self.write_file(self.server.media_dir / "test-video.mp4")
            return

        if parsed.path.startswith("/media/compatibility/"):
            filename = urllib.parse.unquote(parsed.path.rsplit("/", 1)[-1])
            if filename not in COMPATIBILITY_FIXTURE_NAMES:
                self.write_json({"error": "media_not_found"}, status=404)
                return
            self.write_file(self.server.media_dir / filename)
            return


        if parsed.path == "/media/test-subtitle.srt":
            self.write_file(self.server.fixture_dir / "test-subtitle.srt")
            return

        self.write_json({"error": "not_found", "path": parsed.path}, status=404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/play":
            self.handle_create_play_session()
            return

        if parsed.path == "/api/progress":
            self.handle_progress()
            return
        self.write_json({"error": "not_found", "path": parsed.path}, status=404)

    def read_json_body(self):
        length = int(self.headers.get("Content-Length") or 0)
        try:
            return json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self.write_json({"error": "bad_json"}, status=400)
            return None

    def handle_create_play_session(self):
        payload = self.read_json_body()
        if payload is None:
            return

        stream_id = payload.get("stream_id")
        if not stream_id:
            self.write_json({"error": "missing_stream_id"}, status=400)
            return

        stream = self.server.stream_cache.get(stream_id)
        if not stream:
            self.write_json({"error": "stream_not_found"}, status=404)
            return

        url = stream.get("url")
        if not url:
            self.write_json({"error": "stream_not_playable"}, status=409)
            return

        try:
            compatibility = self.preflight_stream(stream_id, stream)
        except playback_compatibility.ProbeError as exc:
            self.write_json(
                {"error": "media_preflight_failed", "message": str(exc)},
                status=502,
            )
            return
        if compatibility["status"] == "unsupported":
            self.write_json(
                {
                    "error": "unsupported_media",
                    "message": compatibility["message"],
                    "compatibility": compatibility,
                },
                status=409,
            )
            return

        duration_seconds = compatibility.get("duration_seconds") or stream.get(
            "duration_seconds", 0
        )
        session_id = self.server.play_sessions.create(
            {
                "stream_id": stream_id,
                "url": url,
                "name": stream.get("name", ""),
                "duration_seconds": duration_seconds,
                "compatibility": compatibility,
            }
        )

        self.write_json(
            {
                "url": f"http://{self.server.public_host}:{self.server.server_port}/play/{session_id}",
                "session_id": session_id,
                "stream_id": stream_id,
                "duration_seconds": duration_seconds,
                "compatibility": compatibility,
            }
        )

    def preflight_stream(self, stream_id, stream):
        del stream_id
        cached = self.server.probe_cache.get(stream["url"])
        if cached:
            return cached

        if self.server.ffprobe_path:
            data = playback_compatibility.probe_media(
                self.server.ffprobe_path,
                stream["url"],
                timeout=self.server.probe_timeout,
            )
            compatibility = playback_compatibility.classify_probe(data)
        else:
            compatibility = dict(stream.get("compatibility") or {})
            if not compatibility:
                compatibility = {
                    "status": "candidate",
                    "message": "Media preflight is unavailable",
                }
        self.server.probe_cache.set(stream["url"], compatibility)
        return compatibility

    def handle_progress(self):
        payload = self.read_json_body()
        if payload is None:
            return
        try:
            item = self.server.progress_store.update(payload)
        except (OSError, ValueError) as exc:
            self.write_json({"error": "invalid_progress", "message": str(exc)}, status=400)
            return
        self.write_json({"saved": item is not None, "item": item})

    def handle_search(self, parsed):
        query = urllib.parse.parse_qs(parsed.query).get("q", [""])[0].strip()
        if not query:
            self.write_json({"query": "", "count": 0, "items": [], "results": []})
            return

        if query.lower() in {
            "pocketstremio test series",
            "test series",
            "offline test series",
        }:
            summary = {
                key: value for key, value in TEST_SERIES_META.items() if key != "videos"
            }
            item = normalize_meta(summary)
            items = [item]
            self.write_json(
                {"query": query, "count": len(items), "items": items, "results": items}
            )
            return

        extra = urllib.parse.quote(f"search={query}", safe="=")
        catalogs = []
        failures = []
        catalog_successes = 0
        for item_type in ("movie", "series"):
            url = f"{CINEMETA_BASE}/catalog/{item_type}/top/{extra}.json"
            try:
                data = fetch_json(url)
                catalogs.append(
                    [normalize_meta(meta) for meta in data.get("metas", [])[:12]]
                )
                catalog_successes += 1
            except Exception as exc:
                failures.append(exc)
                catalogs.append([])

        if catalog_successes == 0:
            message = str(failures[0]) if failures else "No search catalog responded"
            self.write_json({"error": "search_failed", "message": message}, status=502)
            return

        items = []
        seen = set()
        for index in range(max(len(catalog) for catalog in catalogs)):
            for catalog in catalogs:
                if index >= len(catalog):
                    continue
                item = catalog[index]
                key = (item.get("type"), item.get("id"))
                if not item.get("id") or key in seen:
                    continue
                seen.add(key)
                items.append(item)
                if len(items) >= 12:
                    break
            if len(items) >= 12:
                break

        if "bunny" in query.lower() or "big buck" in query.lower():
            try:
                bbb = normalize_meta(
                    fetch_json(
                        f"{CINEMETA_BASE}/meta/movie/{BIG_BUCK_BUNNY_ID}.json"
                    ).get("meta")
                    or {}
                )
                if bbb.get("id") and all(item.get("id") != bbb["id"] for item in items):
                    items.insert(0, bbb)
            except Exception:
                pass

        self.write_json({"query": query, "count": len(items), "items": items, "results": items})

    def handle_meta(self, item_type, item_id):
        if item_type == "series" and item_id == TEST_SERIES_ID:
            self.write_json(normalize_meta(TEST_SERIES_META))
            return
        if item_type == "series" and item_id in TEST_SERIES_EPISODES:
            self.write_json(normalize_test_episode(item_id))
            return

        episode_parts = (
            split_episode_video_id(item_id) if item_type == "series" else None
        )
        if episode_parts:
            series_id = episode_parts[0]
            url = (
                f"{CINEMETA_BASE}/meta/series/"
                f"{urllib.parse.quote(series_id)}.json"
            )
            try:
                data = fetch_json(url)
                episode_meta = normalize_series_episode(
                    data.get("meta") or {}, item_id
                )
            except Exception as exc:
                self.write_json(
                    {"error": "meta_failed", "message": str(exc)}, status=502
                )
                return
            if not episode_meta:
                self.write_json(
                    {"error": "not_found", "message": "Episode details unavailable"},
                    status=404,
                )
                return
            self.write_json(episode_meta)
            return

        url = f"{CINEMETA_BASE}/meta/{urllib.parse.quote(item_type)}/{urllib.parse.quote(item_id)}.json"
        try:
            data = fetch_json(url)
            meta = normalize_meta(data.get("meta") or {})
        except Exception as exc:
            self.write_json({"error": "meta_failed", "message": str(exc)}, status=502)
            return
        self.write_json(meta)

    def handle_streams(self, item_type, item_id):
        streams = []
        failures = []

        if item_type == "movie" and item_id == BIG_BUCK_BUNNY_ID:
            for fixture in COMPATIBILITY_FIXTURES:
                path = self.server.media_dir / fixture["filename"]
                if not path.is_file() and not fixture.get("required"):
                    continue
                stream_url = (
                    f"http://{self.server.public_host}:{self.server.server_port}"
                    f"/media/compatibility/{urllib.parse.quote(fixture['filename'])}"
                )
                streams.append(
                    {
                        "id": f"fixture-{Path(fixture['filename']).stem}",
                        "name": fixture["name"],
                        "description": fixture["description"],
                        "duration_seconds": fixture["duration_seconds"],
                        "playable": path.is_file(),
                        "compatibility": fixture["compatibility"],
                        "source": "pocketstremio-compatibility-fixture",
                        "url": stream_url if path.is_file() else "",
                    }
                )

        if item_type == "series" and item_id in TEST_SERIES_EPISODES:
            fixture = SERIES_PLAYBACK_FIXTURE
            path = self.server.media_dir / fixture["filename"]
            if not path.is_file():
                fixture = COMPATIBILITY_FIXTURES[0]
                path = self.server.media_dir / fixture["filename"]
            stream_url = (
                f"http://{self.server.public_host}:{self.server.server_port}"
                f"/media/compatibility/{urllib.parse.quote(fixture['filename'])}"
            )
            streams.append(
                {
                    "id": f"series-fixture-{hashlib.sha1(item_id.encode()).hexdigest()[:8]}",
                    "name": fixture["name"],
                    "description": fixture["description"],
                    "duration_seconds": fixture["duration_seconds"],
                    "playable": path.is_file(),
                    "compatibility": fixture["compatibility"],
                    "source": "pocketstremio-series-fixture",
                    "url": stream_url if path.is_file() else "",
                }
            )

        for addon_index, addon in enumerate(self.server.stream_addons):
            manifest_url = addon["manifest_url"]
            try:
                manifest = self.server.manifest_cache.get(manifest_url)
                if manifest is None:
                    manifest = fetch_json(manifest_url)
                    self.server.manifest_cache[manifest_url] = manifest
                if not manifest_supports(manifest, "stream", item_type):
                    continue
            except Exception as exc:
                source = addon.get("name") or "stream source"
                print(f"stream addon manifest failed: {manifest_url}: {exc}", flush=True)
                failures.append({"source": source, "message": f"{source} is unavailable"})
                continue

            base = addon_base_from_manifest(manifest_url)
            url = f"{base}/stream/{urllib.parse.quote(item_type)}/{urllib.parse.quote(item_id)}.json"
            try:
                data = fetch_json(url)
            except Exception as exc:
                print(f"stream addon failed: {manifest_url}: {exc}", flush=True)
                source = addon.get("name") or "stream source"
                failures.append({"source": source, "message": f"{source} is unavailable"})
                continue

            for stream_index, raw in enumerate(data.get("streams", [])):
                stream_url = raw.get("url")
                behavior_hints = raw.get("behaviorHints") or {}
                compatibility = playback_compatibility.declared_compatibility(
                    behavior_hints
                )
                stream_id = f"a{addon_index}-s{stream_index}-{hashlib.sha1((stream_url or repr(raw)).encode()).hexdigest()[:8]}"
                playable = bool(
                    stream_url
                    and stream_url.startswith(("http://", "https://"))
                    and compatibility["status"] != "unsupported"
                )
                if stream_url and compatibility["status"] == "unsupported":
                    failures.append(
                        {
                            "source": addon.get("name") or "stream source",
                            "message": compatibility["message"],
                        }
                    )
                streams.append(
                    {
                        "id": stream_id,
                        "name": raw.get("name") or raw.get("title") or f"Stream {stream_index + 1}",
                        "description": raw.get("description") or "",
                        "label": stream_label(raw, f"Stream {stream_index + 1}"),
                        "playable": playable,
                        "compatibility": compatibility,
                        "source": addon.get("name") or manifest_url,
                        "url": stream_url if playable else "",
                        "video_hash": behavior_hints.get("videoHash") or "",
                        "video_size": behavior_hints.get("videoSize") or 0,
                        "duration_seconds": nonnegative_int(raw.get("durationSeconds")),
                    }
                )

        for stream in streams:
            self.server.stream_cache[stream["id"]] = stream

        public_items = [
            {
                k: v
                for k, v in stream.items()
                if k not in {"url", "source", "video_hash", "video_size"}
            }
            for stream in streams
        ]
        self.write_json({"count": len(public_items), "items": public_items, "failures": failures})

    def handle_subtitles(self, item_type, item_id, parsed):
        query = urllib.parse.parse_qs(parsed.query)
        stream = self.server.stream_cache.get(query.get("stream_id", [""])[0], {})
        subtitles = []

        if item_type == "movie" and item_id == BIG_BUCK_BUNNY_ID:
            fixture = self.server.fixture_dir / "test-subtitle.srt"
            if fixture.is_file():
                subtitles.append(
                    {
                        "id": f"sample-sub-{BIG_BUCK_BUNNY_ID}",
                        "name": "English (PocketStremio test)",
                        "lang": "eng",
                        "source": "pocketstremio-sample",
                        "url": f"http://{self.server.public_host}:{self.server.server_port}/media/test-subtitle.srt",
                    }
                )

        for addon_index, addon in enumerate(self.server.stream_addons):
            base = addon_base_from_manifest(addon["manifest_url"])
            routes = [
                f"{base}/subtitles/{urllib.parse.quote(item_type)}/{urllib.parse.quote(item_id)}.json"
            ]
            video_hash = str(stream.get("video_hash") or "")
            video_size = stream.get("video_size") or 0
            if video_hash:
                extra = urllib.parse.quote(
                    f"videoID={item_id}&videoSize={video_size}",
                    safe="=&",
                )
                routes.insert(
                    0,
                    f"{base}/subtitles/{urllib.parse.quote(item_type)}/{urllib.parse.quote(video_hash)}/{extra}.json",
                )

            seen_addon_urls = set()
            for route in routes:
                try:
                    data = fetch_json(route)
                except Exception as exc:
                    print(f"subtitle addon failed: {route}: {exc}", flush=True)
                    continue

                for raw in data.get("subtitles", []):
                    subtitle_url = raw.get("url")
                    if not subtitle_url or not subtitle_url.startswith(("http://", "https://")):
                        continue
                    if subtitle_url in seen_addon_urls:
                        continue
                    seen_addon_urls.add(subtitle_url)
                    subtitle_id = (
                        f"a{addon_index}-sub-"
                        f"{hashlib.sha1(subtitle_url.encode()).hexdigest()[:10]}"
                    )
                    lang = str(raw.get("lang") or raw.get("language") or "und")
                    subtitles.append(
                        {
                            "id": subtitle_id,
                            "name": raw.get("name") or lang,
                            "lang": lang,
                            "source": addon.get("name") or addon["manifest_url"],
                            "url": subtitle_url,
                        }
                    )

        for subtitle in subtitles:
            self.server.subtitle_cache[subtitle["id"]] = subtitle
        public_items = [
            {k: v for k, v in subtitle.items() if k not in {"url", "source"}}
            for subtitle in subtitles
        ]
        self.write_json({"count": len(public_items), "items": public_items})

    def handle_play_session(self, session_id):
        session, expired = self.server.play_sessions.get(session_id)
        if not session:
            if expired:
                self.write_json(
                    {"error": "session_expired", "message": "Playback session expired"},
                    status=410,
                )
            else:
                self.write_json({"error": "session_not_found"}, status=404)
            return
        self.proxy_remote_url(session["url"])

    def handle_subtitle(self, subtitle_id):
        subtitle = self.server.subtitle_cache.get(subtitle_id)
        if not subtitle:
            self.write_json({"error": "subtitle_not_found"}, status=404)
            return
        self.proxy_remote_url(subtitle["url"])

    def proxy_remote_url(self, url):
        headers = {"User-Agent": "PocketStremio/0.4", "Accept-Encoding": "identity"}
        if self.headers.get("Range"):
            headers["Range"] = self.headers["Range"]

        req = urllib.request.Request(url, headers=headers)
        response_started = False
        try:
            with urllib.request.urlopen(req, timeout=MEDIA_TIMEOUT) as resp:
                self.send_response(resp.status)
                for key in [
                    "Content-Type",
                    "Content-Length",
                    "Content-Range",
                    "Accept-Ranges",
                    "Cache-Control",
                    "ETag",
                    "Last-Modified",
                ]:
                    value = resp.headers.get(key)
                    if value:
                        self.send_header(key, value)
                self.send_header("Connection", "close")
                self.end_headers()
                response_started = True
                while True:
                    chunk = resp.read(1024 * 256)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
        except urllib.error.HTTPError as exc:
            if not response_started:
                self.write_json({"error": "upstream_http_error", "status": exc.code}, status=502)
        except (BrokenPipeError, ConnectionResetError):
            print("playback client disconnected", flush=True)
        except Exception as exc:
            if response_started:
                print(f"upstream stream interrupted: {exc}", flush=True)
            else:
                self.write_json(
                    {"error": "upstream_fetch_failed", "message": "Stream source is unavailable"},
                    status=502,
                )
        finally:
            self.close_connection = True

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args), flush=True)

    def write_json(self, payload, status=200):
        body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def write_file(self, path):
        if not path.is_file():
            self.write_json(
                {
                    "error": "missing_media",
                    "message": "Place a compatible MP4 at server/media/test-video.mp4",
                },
                status=404,
            )
            return

        file_size = path.stat().st_size
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        range_header = self.headers.get("Range", "")
        if range_header.startswith("bytes="):
            start_text, _, end_text = range_header[6:].partition("-")
            try:
                start = int(start_text) if start_text else 0
                end = int(end_text) if end_text else file_size - 1
                end = min(end, file_size - 1)
                if start < 0 or start > end:
                    raise ValueError
            except ValueError:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{file_size}")
                self.end_headers()
                return

            self.send_response(206)
            self.send_header("Content-Type", content_type)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
            self.send_header("Content-Length", str(end - start + 1))
            self.end_headers()
            self.stream_file_range(path, start, end)
            return

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(file_size))
        self.end_headers()
        self.stream_file_range(path, 0, file_size - 1)

    def stream_file_range(self, path, start, end):
        remaining = end - start + 1
        with path.open("rb") as f:
            f.seek(start)
            while remaining > 0:
                chunk = f.read(min(1024 * 256, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)


def main():
    parser = argparse.ArgumentParser(description="Minimal PocketStremio server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8755)
    parser.add_argument("--public-host", default=None)
    parser.add_argument("--stremio-service-url", default="http://127.0.0.1:11470")
    parser.add_argument("--open-media-addon-port", type=int, default=8756)
    parser.add_argument("--disable-open-media-addon", action="store_true")
    parser.add_argument(
        "--ffprobe",
        default=os.environ.get("POCKETSTREMIO_FFPROBE", ""),
        help="Optional ffprobe executable used for media preflight",
    )
    parser.add_argument("--probe-timeout", type=int, default=45)
    parser.add_argument("--probe-cache-ttl", type=int, default=DEFAULT_PROBE_CACHE_TTL)
    parser.add_argument("--max-probe-cache", type=int, default=DEFAULT_MAX_PROBE_CACHE)
    parser.add_argument("--session-ttl", type=int, default=DEFAULT_SESSION_TTL)
    parser.add_argument("--max-sessions", type=int, default=DEFAULT_MAX_SESSIONS)
    parser.add_argument(
        "--stream-addons",
        default=str(Path(__file__).resolve().parent / "config" / "stream_addons.json"),
    )
    parser.add_argument(
        "--media-dir",
        default=str(Path(__file__).resolve().parent / "media"),
        help="Directory containing test-video.mp4 for playback experiments",
    )
    parser.add_argument(
        "--fixture-dir",
        default=str(Path(__file__).resolve().parent / "fixtures"),
        help="Directory containing deterministic text fixtures",
    )
    parser.add_argument(
        "--data-dir",
        default=str(Path(__file__).resolve().parent / "data"),
        help="Directory for persistent server state",
    )
    args = parser.parse_args()

    media_dir = Path(args.media_dir).resolve()
    media_dir.mkdir(parents=True, exist_ok=True)
    fixture_dir = Path(args.fixture_dir).resolve()
    data_dir = Path(args.data_dir).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)

    httpd = ThreadingHTTPServer((args.host, args.port), PocketStremioHandler)
    httpd.media_dir = media_dir
    httpd.fixture_dir = fixture_dir
    httpd.public_host = args.public_host or args.host
    httpd.server_port = args.port
    httpd.stremio_service_url = args.stremio_service_url.rstrip("/") if args.stremio_service_url else ""
    httpd.stream_addons = load_stream_addons(args.stream_addons, httpd.stremio_service_url)
    open_media_server = None
    open_media_thread = None
    if not args.disable_open_media_addon:
        open_media_server = open_media_addon.create_server("127.0.0.1", args.open_media_addon_port)
        open_media_thread = threading.Thread(target=open_media_server.serve_forever, daemon=True)
        open_media_thread.start()
        httpd.stream_addons.append(
            {
                "name": "PocketStremio Open Media",
                "manifest_url": f"http://127.0.0.1:{args.open_media_addon_port}/manifest.json",
            }
        )
    httpd.stream_cache = {}
    httpd.subtitle_cache = {}
    httpd.play_sessions = SessionStore(args.session_ttl, args.max_sessions)
    httpd.manifest_cache = {}
    httpd.probe_cache = ProbeCache(
        data_dir / "probe_cache.json", args.probe_cache_ttl, args.max_probe_cache
    )
    httpd.ffprobe_path = playback_compatibility.resolve_ffprobe(args.ffprobe)
    httpd.probe_timeout = max(1, args.probe_timeout)
    httpd.progress_store = ProgressStore(data_dir / "continue_watching.json")
    httpd.started_at = time.time()
    httpd.daemon_threads = True

    print(f"PocketStremio server listening on http://{args.host}:{args.port}", flush=True)
    print(f"Public host: {httpd.public_host}", flush=True)
    print(f"Stream addons configured: {len(httpd.stream_addons)}", flush=True)
    print(f"Media preflight: {httpd.ffprobe_path or 'disabled'}", flush=True)
    print(
        f"Play sessions: ttl={httpd.play_sessions.ttl_seconds}s "
        f"max={httpd.play_sessions.max_items}",
        flush=True,
    )
    if open_media_server:
        print(
            f"Open-media addon: http://127.0.0.1:{args.open_media_addon_port}/manifest.json",
            flush=True,
        )
    print(f"Media directory: {media_dir}", flush=True)
    print(f"Data directory: {data_dir}", flush=True)
    try:
        httpd.serve_forever()
    finally:
        httpd.server_close()
        if open_media_server:
            open_media_server.shutdown()
            open_media_server.server_close()
            open_media_thread.join(timeout=5)


if __name__ == "__main__":
    main()
