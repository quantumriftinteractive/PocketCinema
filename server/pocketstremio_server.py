#!/usr/bin/env python3
import argparse
import hashlib
import json
import mimetypes
import os
import re
import secrets
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

try:
    from server import hls_relay
    from server import link_stremio_account
    from server import open_media_addon
    from server import playback_compatibility
    from server import stremio_account
    from server import stremio_service
    from server import transcoding
except ImportError:
    import hls_relay
    import link_stremio_account
    import open_media_addon
    import playback_compatibility
    import stremio_account
    import stremio_service
    import transcoding


CINEMETA_BASE = "https://v3-cinemeta.strem.io"
SERVER_VERSION = "0.16.1-subtitle-sync"
DEFAULT_TIMEOUT = 15
MEDIA_TIMEOUT = 30
BIG_BUCK_BUNNY_ID = "tt1254207"
TEST_SERIES_ID = "pocketstremio-test-series"
MAX_CONTINUE_ITEMS = 50
DEFAULT_SESSION_TTL = 6 * 60 * 60
DEFAULT_MAX_SESSIONS = 128
DEFAULT_PROBE_CACHE_TTL = 7 * 24 * 60 * 60
DEFAULT_MAX_PROBE_CACHE = 256
MAX_LIVE_TV_ITEMS = 128
MAX_SUBTITLE_BYTES = 2 * 1024 * 1024
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
    {
        "filename": "subtitle-switch-fixture.mkv",
        "name": "Subtitle switching test - two embedded tracks",
        "description": "H.264/AAC Matroska | 640x360 | two English SubRip tracks",
        "duration_seconds": 20,
        "compatibility": {
            "status": "candidate",
            "message": "Capability test: embedded subtitle tracks are not physically confirmed",
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


def load_stream_addons(config_path):
    addons = []
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


class PublicMediaRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        resolved = urllib.parse.urljoin(req.full_url, newurl)
        if not stremio_account.validate_direct_stream_url(resolved):
            raise urllib.error.URLError("Blocked media redirect")
        return super().redirect_request(req, fp, code, msg, headers, resolved)


def open_media_url(url, headers, timeout, validate_public=False):
    if validate_public and not stremio_account.validate_direct_stream_url(url):
        raise urllib.error.URLError("Blocked media address")
    request = urllib.request.Request(url, headers=headers)
    if validate_public:
        return urllib.request.build_opener(PublicMediaRedirectHandler()).open(
            request, timeout=timeout
        )
    return urllib.request.urlopen(request, timeout=timeout)


def release_year(value):
    release = str(value or "")
    for token in release.replace("-", " ").split():
        if len(token) >= 4 and token[:4].isdigit():
            return int(token[:4])
    return None


def safe_addon_text(value, fallback="", maximum=240):
    text = " ".join(str(value or "").split())
    if any(marker in text.lower() for marker in ("http://", "https://", "file://")):
        return fallback
    return text[:maximum] or fallback


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


def stream_release_label(stream):
    """Return safe release identity hints for the device selector."""
    filename = str(stream.get("video_filename") or "")
    if filename:
        filename = re.split(r"[\\/]", filename)[-1]
        stem = Path(filename).stem
        tokens = []
        for pattern in (
            r"S\d{1,2}E\d{1,2}",
            r"(?:2160|1080|720|576|480|360)p",
            r"WEB[- ]?DL",
            r"WEBRip",
            r"BluRay",
            r"HDTV",
            r"AMZN",
            r"NF",
            r"HMAX",
            r"(?:x|h)26[45]",
            r"HEVC",
            r"(?:AAC|EAC3|DDP?)",
        ):
            match = re.search(pattern, stem, re.IGNORECASE)
            if match:
                value = match.group(0).replace("-", "-").upper()
                if value not in tokens:
                    tokens.append(value)
        group = re.search(r"-([A-Za-z0-9][A-Za-z0-9]{1,11})$", stem)
        if group:
            tokens.append(group.group(1))
        if tokens:
            return " ".join(tokens)[:55]
        return safe_addon_text(stem, "", 55)
    return safe_addon_text(stream.get("description"), "", 120)


def account_stream_quality_rank(stream):
    if not str(stream.get("source") or "").startswith("Stremio account:"):
        return 0, 0
    text = " ".join(
        str(stream.get(key) or "") for key in ("name", "label", "description")
    ).lower()
    markers = ("360p", "480p", "576p", "dvdrip", "720p", "1080p", "2160p", "4k")
    for rank, marker in enumerate(markers):
        if marker in text:
            return 1, rank
    return 1, 5


def subtitle_match_rank(raw, stream):
    subtitle_text = safe_addon_text(
        raw.get("title") or raw.get("name"), "", 300
    ).lower()
    stream_text = str(stream.get("subtitle_match_text") or "").lower()
    subtitle_tokens = set(re.findall(r"[a-z0-9]+", subtitle_text))
    stream_tokens = set(re.findall(r"[a-z0-9]+", stream_text))
    overlap = len(subtitle_tokens & stream_tokens)
    resolution_tokens = {"360p", "480p", "576p", "720p", "1080p", "2160p", "4k"}
    subtitle_resolutions = subtitle_tokens & resolution_tokens
    stream_resolutions = stream_tokens & resolution_tokens
    resolution_score = 0
    if subtitle_resolutions and stream_resolutions:
        resolution_score = 4 if subtitle_resolutions & stream_resolutions else -4
    video_hash = str(stream.get("video_hash") or "").lower()
    hash_score = 100 if video_hash and str(raw.get("moviehash") or "").lower() == video_hash else 0
    trusted_score = 2 if raw.get("from_trusted") is True else 0
    return -(hash_score + resolution_score + overlap + trusted_score)


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
        return hashlib.sha256(("v2\0" + url).encode()).hexdigest()

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
            with self.server.hls_bridge_lock:
                active_hls_bridges = self.server.active_hls_bridges
            with self.server.transcode_state_lock:
                active_transcodes = self.server.active_transcodes
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
                    "live_bridges": {"active": active_hls_bridges},
                    "transcodes": {
                        "active": active_transcodes,
                        "available": bool(self.server.ffmpeg_path),
                        "maximum": 1,
                    },
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
                    "stremio_service": self.server.stremio_service.status(),
                    "stremio_account": self.server.stremio_account.status(),
                }
            )
            return

        if parsed.path == "/api/search":
            self.handle_search(parsed)
            return

        if parsed.path == "/api/addons":
            self.handle_account_addons(parsed)
            return

        if parsed.path == "/api/live-tv":
            self.handle_live_tv()
            return

        if parsed.path == "/api/account":
            self.handle_account_status(parsed)
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
            self.handle_subtitle(parts[1], parsed)
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
        if parsed.path == "/api/account/link":
            self.handle_account_link()
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
        local_path = stream.get("local_path")
        if not url and not local_path:
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

        subtitle_id = str(payload.get("subtitle_id") or "")
        subtitle = None
        if subtitle_id and subtitle_id != "none":
            subtitle = self.server.subtitle_cache.get(subtitle_id)
            if not subtitle:
                self.write_json({"error": "subtitle_not_found"}, status=404)
                return

        field_test = bool(payload.get("field_test")) and getattr(
            self.server, "field_test_enabled", False
        )
        field_test_subtitles = []
        if field_test and subtitle:
            field_test_subtitles.append(subtitle)
            for candidate in self.server.subtitle_cache.values():
                if (
                    candidate.get("item_type") == payload.get("type")
                    and candidate.get("item_id") == payload.get("id")
                    and candidate.get("id") != subtitle.get("id")
                ):
                    field_test_subtitles.append(candidate)
                    if len(field_test_subtitles) >= 2:
                        break
            if subtitle.get("item_type") != payload.get("type") or subtitle.get(
                "item_id"
            ) != payload.get("id"):
                self.write_json({"error": "subtitle_mismatch"}, status=409)
                return

        start_seconds = nonnegative_int(payload.get("resume_seconds"))
        transcode = bool(subtitle) or transcoding.needs_downscale(compatibility)
        if transcode and not self.server.ffmpeg_path:
            self.write_json(
                {
                    "error": "transcoding_unavailable",
                    "message": "Subtitle and downscaling service is unavailable",
                },
                status=503,
            )
            return

        duration_seconds = compatibility.get("duration_seconds") or stream.get(
            "duration_seconds", 0
        )
        session_data = {
            "stream_id": stream_id,
            "url": url,
            "local_path": local_path,
            "name": stream.get("name", ""),
            "duration_seconds": duration_seconds,
            "compatibility": compatibility,
            "hls": compatibility.get("container") == "hls",
        }
        if transcode:
            source_session_id = self.server.play_sessions.create(session_data)
            source_url = (
                f"http://{self.server.public_host}:{self.server.server_port}"
                f"/play/{source_session_id}"
            )
            session_data = {
                "stream_id": stream_id,
                "name": stream.get("name", ""),
                "duration_seconds": duration_seconds,
                "compatibility": compatibility,
                "transcode": True,
                "source_url": source_url,
                "subtitle_url": subtitle.get("url", "") if subtitle else "",
                "subtitle_path": subtitle.get("local_path", "") if subtitle else "",
                "start_seconds": start_seconds,
                "field_test": field_test,
                "field_test_subtitles": field_test_subtitles,
            }
        session_id = self.server.play_sessions.create(session_data)

        self.write_json(
            {
                "url": f"http://{self.server.public_host}:{self.server.server_port}/play/{session_id}",
                "session_id": session_id,
                "stream_id": stream_id,
                "duration_seconds": duration_seconds,
                "compatibility": compatibility,
                "transcoded": transcode,
                "server_seek_applied": bool(transcode and start_seconds),
            }
        )

    def preflight_stream(self, stream_id, stream):
        del stream_id
        probe_target = stream.get("local_path") or stream.get("url")
        cached = self.server.probe_cache.get(probe_target)
        if cached:
            return cached

        if self.server.ffprobe_path:
            data = playback_compatibility.probe_media(
                self.server.ffprobe_path,
                probe_target,
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
        self.server.probe_cache.set(probe_target, compatibility)
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

    def handle_account_addons(self, parsed):
        query = urllib.parse.parse_qs(parsed.query)
        force = query.get("refresh", [""])[0].lower() in {"1", "true", "yes"}
        try:
            self.write_json(
                self.server.stremio_account.public_collection(force=force)
            )
        except stremio_account.StremioAccountError as exc:
            self.write_json(
                {"error": "stremio_account_unavailable", "message": str(exc)},
                status=502,
            )

    def handle_account_status(self, parsed):
        query = urllib.parse.parse_qs(parsed.query)
        poll = query.get("poll", [""])[0].lower() in {"1", "true", "yes"}
        try:
            link = self.server.stremio_link.status(poll=poll)
            self.write_json(
                {"account": self.server.stremio_account.status(), "link": link}
            )
        except Exception:
            self.write_json(
                {
                    "error": "account_link_unavailable",
                    "message": "Stremio account linking is unavailable",
                },
                status=502,
            )

    def handle_account_link(self):
        try:
            self.write_json(self.server.stremio_link.start(), status=201)
        except RuntimeError as exc:
            self.write_json(
                {"error": "account_already_connected", "message": str(exc)},
                status=409,
            )
        except Exception:
            self.write_json(
                {
                    "error": "account_link_unavailable",
                    "message": "Could not create a Stremio account link",
                },
                status=502,
            )

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

    def handle_live_tv(self):
        items = []
        failures = []
        seen = set()
        try:
            catalogs = self.server.stremio_account.catalog_sources("tv")
        except stremio_account.StremioAccountError as exc:
            catalogs = []
            failures.append({"source": "Stremio account", "message": str(exc)})

        for catalog in catalogs:
            source = catalog["source"]
            source_name = safe_addon_text(source["name"], "Account addon", 120)
            try:
                metas = self.server.stremio_account.fetch_catalog(
                    source, "tv", catalog["id"]
                )
            except stremio_account.StremioAccountError as exc:
                failures.append({"source": source_name, "message": str(exc)})
                continue
            for raw in metas:
                if not isinstance(raw, dict):
                    continue
                item_id = str(raw.get("id") or "").strip()[:160]
                if not item_id or item_id in seen:
                    continue
                seen.add(item_id)
                items.append(
                    {
                        "id": item_id,
                        "type": "tv",
                        "title": safe_addon_text(
                            raw.get("name"), "Live channel", 160
                        ),
                        "source": source_name,
                    }
                )
                if len(items) >= MAX_LIVE_TV_ITEMS:
                    break
            if len(items) >= MAX_LIVE_TV_ITEMS:
                break

        self.write_json(
            {"count": len(items), "items": items, "failures": failures}
        )

    def handle_streams(self, item_type, item_id):
        streams = []
        failures = []

        try:
            service_result = self.server.stremio_service.resolve_streams(
                item_type, item_id
            )
            for service_index, raw in enumerate(service_result["items"]):
                local_path = raw["local_path"]
                stream_id = (
                    f"stremio-local-{service_index}-"
                    f"{hashlib.sha1(local_path.encode()).hexdigest()[:8]}"
                )
                streams.append(
                    {
                        "id": stream_id,
                        "name": raw["name"],
                        "description": raw["description"],
                        "label": raw["name"],
                        "playable": True,
                        "compatibility": {
                            "status": "candidate",
                            "message": "Local file requires media preflight",
                        },
                        "source": "Stremio Service Local Files",
                        "local_path": local_path,
                        "duration_seconds": 0,
                    }
                )
            if service_result["message"]:
                failures.append(
                    {
                        "source": "Stremio Service Local Files",
                        "message": service_result["message"],
                    }
                )
        except stremio_service.StremioServiceError as exc:
            print(f"Stremio Service stream lookup failed: {exc}", flush=True)
            failures.append(
                {
                    "source": "Stremio Service Local Files",
                    "message": str(exc),
                }
            )

        try:
            account_sources = self.server.stremio_account.stream_sources(item_type)
        except stremio_account.StremioAccountError as exc:
            account_sources = []
            failures.append({"source": "Stremio account", "message": str(exc)})

        for source in account_sources:
            source_name = safe_addon_text(source["name"], "Account addon", 120)
            try:
                raw_streams = self.server.stremio_account.fetch_streams(
                    source, item_type, item_id
                )
            except stremio_account.StremioAccountError as exc:
                failures.append({"source": source_name, "message": str(exc)})
                continue

            rejected = False
            for stream_index, raw in enumerate(raw_streams):
                if not isinstance(raw, dict):
                    rejected = True
                    continue
                if stremio_account.has_unsupported_stream_shape(raw):
                    rejected = True
                    continue
                stream_url = raw.get("url")
                if not stremio_account.validate_direct_stream_url(stream_url):
                    rejected = True
                    continue
                behavior_hints = raw.get("behaviorHints") or {}
                compatibility = playback_compatibility.declared_compatibility(
                    behavior_hints
                )
                if compatibility["status"] == "unsupported":
                    failures.append(
                        {"source": source_name, "message": compatibility["message"]}
                    )
                    continue
                stream_name = safe_addon_text(
                    raw.get("name") or raw.get("title"),
                    f"{source_name} - Stream {stream_index + 1}",
                    160,
                )
                stream_id = (
                    f"u{source['key']}-s{stream_index}-"
                    f"{hashlib.sha1(stream_url.encode()).hexdigest()[:8]}"
                )
                streams.append(
                    {
                        "id": stream_id,
                        "name": stream_name,
                        "description": safe_addon_text(raw.get("description"), ""),
                        "label": stream_name,
                        "playable": True,
                        "compatibility": compatibility,
                        "source": f"Stremio account: {source_name}",
                        "url": stream_url,
                        "video_hash": behavior_hints.get("videoHash") or "",
                        "video_size": behavior_hints.get("videoSize") or 0,
                        "video_filename": safe_addon_text(
                            behavior_hints.get("filename"), "", 240
                        ),
                        "subtitle_match_text": safe_addon_text(
                            raw.get("title") or behavior_hints.get("filename"),
                            "",
                            300,
                        ),
                        "duration_seconds": nonnegative_int(raw.get("durationSeconds")),
                        "release_label": stream_release_label(
                            {
                                "video_filename": behavior_hints.get("filename"),
                                "description": raw.get("description"),
                            }
                        ),
                    }
                )
            if rejected:
                failures.append(
                    {
                        "source": source_name,
                        "message": "Unsupported P2P, external-player, private-address, or non-HTTP account stream was ignored",
                    }
                )

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
                        "video_filename": safe_addon_text(
                            behavior_hints.get("filename"), "", 240
                        ),
                        "release_label": stream_release_label(
                            {
                                "video_filename": behavior_hints.get("filename"),
                                "description": raw.get("description"),
                            }
                        ),
                    }
                )

        streams.sort(key=account_stream_quality_rank)
        for stream in streams:
            probe_target = stream.get("local_path") or stream.get("url")
            cached_compatibility = (
                self.server.probe_cache.get(probe_target) if probe_target else None
            )
            if cached_compatibility:
                stream["compatibility"] = cached_compatibility
                if cached_compatibility.get("status") == "unsupported":
                    stream["playable"] = False
            stream["playback_mode"] = transcoding.playback_mode(
                stream.get("compatibility") or {}
            )
            stream["release_label"] = stream_release_label(stream)
            self.server.stream_cache[stream["id"]] = stream

        public_items = [
            {
                k: v
                for k, v in stream.items()
                if k
                not in {
                    "url",
                    "local_path",
                    "source",
                    "video_hash",
                    "video_size",
                    "video_filename",
                    "subtitle_match_text",
                }
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
                        "local_path": str(fixture.resolve()),
                        "item_type": item_type,
                        "item_id": item_id,
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
                    if not stremio_account.validate_direct_stream_url(subtitle_url):
                        continue
                    if subtitle_url in seen_addon_urls:
                        continue
                    seen_addon_urls.add(subtitle_url)
                    subtitle_id = (
                        f"a{addon_index}-sub-"
                        f"{hashlib.sha1(subtitle_url.encode()).hexdigest()[:10]}"
                    )
                    lang = str(raw.get("lang") or raw.get("language") or "und")
                    if lang.lower() not in {"en", "eng", "english"}:
                        continue
                    subtitles.append(
                        {
                            "id": subtitle_id,
                            "name": safe_addon_text(raw.get("name"), "English"),
                            "lang": lang,
                            "source": addon.get("name") or addon["manifest_url"],
                            "url": subtitle_url,
                            "item_type": item_type,
                            "item_id": item_id,
                        }
                    )

        try:
            account_sources = self.server.stremio_account.subtitle_sources(item_type)
        except stremio_account.StremioAccountError:
            account_sources = []
        seen_account_urls = {subtitle["url"] for subtitle in subtitles}
        seen_account_names = set()
        for source in account_sources:
            subtitle_extra = {
                "videoHash": stream.get("video_hash") or "",
                "videoSize": stream.get("video_size") or 0,
                "filename": stream.get("video_filename") or "",
            }
            try:
                raw_subtitles = self.server.stremio_account.fetch_subtitles(
                    source, item_type, item_id, subtitle_extra
                )
            except stremio_account.StremioAccountError:
                continue
            raw_subtitles.sort(
                key=lambda raw: (
                    subtitle_match_rank(raw, stream)
                    if isinstance(raw, dict)
                    else 999
                )
            )
            for raw in raw_subtitles:
                if not isinstance(raw, dict):
                    continue
                lang = str(raw.get("lang") or raw.get("language") or "und")
                if lang.lower() not in {"en", "eng", "english"}:
                    continue
                subtitle_url = raw.get("url")
                subtitle_name = safe_addon_text(
                    raw.get("title") or raw.get("name"), "English"
                )
                normalized_name = subtitle_name.casefold()
                if (
                    not stremio_account.validate_direct_stream_url(subtitle_url)
                    or subtitle_url in seen_account_urls
                    or normalized_name in seen_account_names
                ):
                    continue
                seen_account_urls.add(subtitle_url)
                seen_account_names.add(normalized_name)
                subtitle_id = (
                    f"u{source['key']}-sub-"
                    f"{hashlib.sha1(subtitle_url.encode()).hexdigest()[:10]}"
                )
                subtitles.append(
                    {
                        "id": subtitle_id,
                        "name": subtitle_name,
                        "lang": "eng",
                        "source": f"Stremio account: {source['name']}",
                        "url": subtitle_url,
                        "item_type": item_type,
                        "item_id": item_id,
                    }
                )
                if len(subtitles) >= 40:
                    break
            if len(subtitles) >= 40:
                break

        for subtitle in subtitles:
            self.server.subtitle_cache[subtitle["id"]] = subtitle
        public_items = [
            {
                k: v
                for k, v in subtitle.items()
                if k
                not in {"url", "local_path", "source", "item_type", "item_id"}
            }
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
        if session.get("transcode"):
            self.stream_transcode(session)
        elif session.get("local_path"):
            local_path = self.server.stremio_service.resolve_local_path(
                session["local_path"]
            )
            if local_path is None:
                self.write_json(
                    {
                        "error": "local_media_unavailable",
                        "message": "Local media is no longer available",
                    },
                    status=404,
                )
                return
            self.write_file(local_path)
        elif session.get("hls"):
            self.stream_hls_transport(session)
        else:
            self.proxy_remote_url(session["url"])

    def download_transcode_subtitle(self, url, local_path=""):
        headers = {
            "User-Agent": "PocketStremio/0.16",
            "Accept-Encoding": "identity",
        }
        if local_path:
            path = Path(local_path).resolve()
            if path != (self.server.fixture_dir / "test-subtitle.srt").resolve():
                raise OSError("Subtitle path is blocked")
            payload = path.read_bytes()[: MAX_SUBTITLE_BYTES + 1]
        else:
            with open_media_url(
                url, headers, MEDIA_TIMEOUT, validate_public=True
            ) as response:
                payload = response.read(MAX_SUBTITLE_BYTES + 1)
        if not payload or len(payload) > MAX_SUBTITLE_BYTES:
            raise OSError("Subtitle download is invalid")
        suffix = transcoding.subtitle_suffix(payload)
        path = self.server.transcode_dir / (
            f"subtitle-{secrets.token_hex(8)}{suffix}"
        )
        path.write_bytes(payload)
        return path

    def stream_transcode(self, session):
        if not self.server.transcode_job_lock.acquire(blocking=False):
            self.write_json(
                {
                    "error": "transcode_busy",
                    "message": "Another converted playback is active",
                },
                status=503,
            )
            return

        process = None
        subtitle_path = None
        subtitle_paths = []
        stderr_thread = None
        stderr_buffer = bytearray()
        response_started = False
        with self.server.transcode_state_lock:
            self.server.active_transcodes += 1
        try:
            subtitle_url = session.get("subtitle_url") or ""
            subtitle_local_path = session.get("subtitle_path") or ""
            if session.get("field_test"):
                for subtitle in session.get("field_test_subtitles", []):
                    subtitle_paths.append(
                        self.download_transcode_subtitle(
                            subtitle.get("url", ""), subtitle.get("local_path", "")
                        )
                    )
                command = transcoding.build_matroska_command(
                    self.server.ffmpeg_path,
                    session["source_url"],
                    [path.name for path in subtitle_paths],
                    session.get("start_seconds", 0),
                )
            else:
                if subtitle_url or subtitle_local_path:
                    subtitle_path = self.download_transcode_subtitle(
                        subtitle_url, subtitle_local_path
                    )
                command = transcoding.build_command(
                    self.server.ffmpeg_path,
                    session["source_url"],
                    subtitle_path.name if subtitle_path else "",
                    session.get("start_seconds", 0),
                )
            process = subprocess.Popen(
                command,
                cwd=self.server.transcode_dir,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )

            def drain_stderr():
                while True:
                    chunk = process.stderr.read(4096)
                    if not chunk:
                        break
                    stderr_buffer.extend(chunk)
                    if len(stderr_buffer) > 32 * 1024:
                        del stderr_buffer[: len(stderr_buffer) - 32 * 1024]

            stderr_thread = threading.Thread(target=drain_stderr, daemon=True)
            stderr_thread.start()
            if session.get("field_test"):
                prefix = process.stdout.read(4)
                if prefix != b"\x1a\x45\xdf\xa3":
                    raise OSError("Field-test playback did not produce Matroska")
            else:
                prefix = process.stdout.read(188 * 3)
                if len(prefix) < 188 * 3 or any(
                    prefix[offset] != 0x47 for offset in (0, 188, 376)
                ):
                    raise OSError("Converted playback did not produce MPEG-TS")

            self.send_response(200)
            self.send_header(
                "Content-Type",
                "video/x-matroska" if session.get("field_test") else "video/mp2t",
            )
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            response_started = True
            self.wfile.write(prefix)
            while True:
                chunk = process.stdout.read(1024 * 256)
                if not chunk:
                    break
                self.wfile.write(chunk)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            print("Transcode playback client disconnected", flush=True)
        except (OSError, urllib.error.URLError, urllib.error.HTTPError) as exc:
            diagnostic = type(exc).__name__
            if process is not None and process.poll() is not None:
                process.wait(timeout=3)
            if stderr_thread is not None:
                stderr_thread.join(timeout=1)
            safe_lines = [
                line
                for line in stderr_buffer.decode("utf-8", "replace").splitlines()
                if "http://" not in line.lower() and "https://" not in line.lower()
            ]
            if safe_lines:
                print(
                    "Transcode diagnostic: " + " | ".join(safe_lines[-4:])[:1000],
                    flush=True,
                )
            if response_started:
                print(f"Transcode interrupted: {diagnostic}", flush=True)
            else:
                self.write_json(
                    {
                        "error": "transcode_failed",
                        "message": "Converted playback could not start",
                    },
                    status=502,
                )
        finally:
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)
            if process is not None and process.stdout is not None:
                process.stdout.close()
            if process is not None and process.stderr is not None:
                process.stderr.close()
            if stderr_thread is not None:
                stderr_thread.join(timeout=1)
            if subtitle_path is not None:
                subtitle_path.unlink(missing_ok=True)
            for path in subtitle_paths:
                path.unlink(missing_ok=True)
            with self.server.transcode_state_lock:
                self.server.active_transcodes -= 1
            self.server.transcode_job_lock.release()
            self.close_connection = True

    def fetch_hls_playlist(self, url):
        headers = {
            "User-Agent": "PocketStremio/0.13",
            "Accept-Encoding": "identity",
        }
        with open_media_url(
            url, headers, MEDIA_TIMEOUT, validate_public=True
        ) as response:
            final_url = response.geturl()
            if not stremio_account.validate_direct_stream_url(final_url):
                raise hls_relay.HlsRelayError(
                    "The HLS playlist redirected to a blocked address"
                )
            payload = response.read(hls_relay.MAX_PLAYLIST_BYTES + 1)
        return final_url, payload

    def fetch_hls_playlist_with_retry(self, url, attempts=3):
        last_error = None
        for attempt in range(attempts):
            try:
                return self.fetch_hls_playlist(url)
            except urllib.error.HTTPError as exc:
                retryable = exc.code in {408, 429} or 500 <= exc.code < 600
                exc.close()
                if not retryable:
                    raise
                last_error = exc
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_error = exc
            if attempt + 1 < attempts:
                time.sleep(attempt + 1)
        raise last_error

    def open_hls_segment_with_retry(self, url, attempts=3):
        headers = {
            "User-Agent": "PocketStremio/0.13",
            "Accept-Encoding": "identity",
        }
        last_error = None
        for attempt in range(attempts):
            response = None
            try:
                response = open_media_url(
                    url,
                    headers,
                    MEDIA_TIMEOUT,
                    validate_public=True,
                )
                prefix = response.read(188 * 3)
                if len(prefix) < 188 * 3 or any(
                    prefix[offset] != 0x47 for offset in (0, 188, 376)
                ):
                    raise hls_relay.HlsRelayError(
                        "The HLS rendition is not MPEG-TS"
                    )
                return response, prefix
            except urllib.error.HTTPError as exc:
                retryable = exc.code in {408, 429} or 500 <= exc.code < 600
                exc.close()
                if not retryable:
                    raise
                last_error = exc
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_error = exc
            except Exception:
                if response is not None:
                    response.close()
                raise
            if response is not None:
                response.close()
            if attempt + 1 < attempts:
                time.sleep(attempt + 1)
        raise last_error

    def stream_hls_transport(self, session):
        playlist_url = session["url"]
        response_started = False
        media_playlist = None
        with self.server.hls_bridge_lock:
            self.server.active_hls_bridges += 1
        try:
            for _ in range(3):
                final_url, payload = self.fetch_hls_playlist_with_retry(playlist_url)
                variant_url = hls_relay.select_variant_url(
                    payload,
                    final_url,
                    stremio_account.validate_direct_stream_url,
                )
                if not variant_url:
                    playlist_url = final_url
                    media_playlist = (final_url, payload)
                    break
                playlist_url = variant_url
            else:
                raise hls_relay.HlsRelayError("The HLS playlist is nested too deeply")

            last_sequence = -1
            expires_at = session["created_at"] + self.server.play_sessions.ttl_seconds
            while time.time() < expires_at:
                if media_playlist:
                    final_url, payload = media_playlist
                    media_playlist = None
                else:
                    final_url, payload = self.fetch_hls_playlist_with_retry(
                        playlist_url
                    )
                media = hls_relay.parse_media_playlist(
                    payload,
                    final_url,
                    stremio_account.validate_direct_stream_url,
                )
                pending = [
                    item
                    for item in media["segments"]
                    if item["sequence"] > last_sequence
                ]
                for segment in pending:
                    response, prefix = self.open_hls_segment_with_retry(
                        segment["url"]
                    )
                    with response:
                        if not response_started:
                            self.send_response(200)
                            self.send_header("Content-Type", "video/mp2t")
                            self.send_header("Cache-Control", "no-store")
                            self.send_header("Connection", "close")
                            self.end_headers()
                            response_started = True
                        self.wfile.write(prefix)
                        while True:
                            chunk = response.read(1024 * 256)
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                    last_sequence = segment["sequence"]
                if media["endlist"]:
                    break
                time.sleep(max(1.0, media["target_duration"] / 2.0))
            if not response_started:
                raise hls_relay.HlsRelayError("The HLS stream has no media segments")
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            print("HLS playback client disconnected", flush=True)
        except (OSError, urllib.error.HTTPError, hls_relay.HlsRelayError) as exc:
            if isinstance(exc, hls_relay.HlsRelayError):
                message = str(exc)
                diagnostic = message
            else:
                message = "The live stream is temporarily unavailable"
                status = getattr(exc, "code", None)
                diagnostic = type(exc).__name__
                if status is not None:
                    diagnostic += f" status={status}"
            if response_started:
                print(f"HLS transport stream interrupted: {diagnostic}", flush=True)
            else:
                self.write_json(
                    {"error": "hls_bridge_failed", "message": message}, status=502
                )
        finally:
            with self.server.hls_bridge_lock:
                self.server.active_hls_bridges -= 1
            self.close_connection = True

    def handle_subtitle(self, subtitle_id, parsed):
        subtitle = self.server.subtitle_cache.get(subtitle_id)
        if not subtitle:
            self.write_json({"error": "subtitle_not_found"}, status=404)
            return
        if (
            getattr(self.server, "field_test_enabled", False)
            and urllib.parse.parse_qs(parsed.query).get("format") == ["matroska"]
        ):
            offset = urllib.parse.parse_qs(parsed.query).get("offset_seconds", ["0"])[0]
            try:
                offset_seconds = max(0, min(int(offset), 24 * 60 * 60))
            except ValueError:
                offset_seconds = 0
            self.stream_subtitle_matroska(subtitle, offset_seconds)
            return
        self.proxy_remote_url(subtitle["url"])

    def stream_subtitle_matroska(self, subtitle, offset_seconds=0):
        subtitle_path = None
        shifted_subtitle_path = None
        process = None
        try:
            subtitle_path = self.download_transcode_subtitle(
                subtitle.get("url", ""), subtitle.get("local_path", "")
            )
            if offset_seconds:
                shifted_subtitle_path = self.server.transcode_dir / (
                    f"subtitle-shifted-{secrets.token_hex(8)}{subtitle_path.suffix}"
                )
                shifted_subtitle_path.write_bytes(
                    transcoding.shift_subtitle_payload(
                        subtitle_path.read_bytes(), offset_seconds
                    )
                )
                subtitle_path.unlink(missing_ok=True)
                subtitle_path = shifted_subtitle_path
                shifted_subtitle_path = None
            input_format = "webvtt" if subtitle_path.suffix == ".vtt" else "srt"
            command = transcoding.build_subtitle_matroska_command(
                self.server.ffmpeg_path, subtitle_path.name, input_format
            )
            process = subprocess.Popen(
                command, cwd=self.server.transcode_dir, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            prefix = process.stdout.read(4)
            if prefix != b"\x1a\x45\xdf\xa3":
                raise OSError("Subtitle packaging did not produce Matroska")
            self.send_response(200)
            self.send_header("Content-Type", "video/x-matroska")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(prefix)
            while True:
                chunk = process.stdout.read(64 * 1024)
                if not chunk:
                    break
                self.wfile.write(chunk)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            print("Subtitle packaging client disconnected", flush=True)
        except (OSError, urllib.error.URLError, urllib.error.HTTPError) as exc:
            if not getattr(self, "_headers_buffer", None):
                self.write_json({"error": "subtitle_packaging_failed"}, status=502)
            print(f"Subtitle packaging failed: {type(exc).__name__}", flush=True)
        finally:
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)
            if process is not None:
                if process.stdout is not None:
                    process.stdout.close()
                if process.stderr is not None:
                    process.stderr.close()
            if subtitle_path is not None:
                subtitle_path.unlink(missing_ok=True)
            if shifted_subtitle_path is not None:
                shifted_subtitle_path.unlink(missing_ok=True)
            self.close_connection = True

    def proxy_remote_url(self, url):
        headers = {"User-Agent": "PocketStremio/0.4", "Accept-Encoding": "identity"}
        if self.headers.get("Range"):
            headers["Range"] = self.headers["Range"]

        response_started = False
        try:
            with open_media_url(url, headers, MEDIA_TIMEOUT) as resp:
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
    parser.add_argument(
        "--stremio-account-config",
        default=str(
            Path(__file__).resolve().parent / "config" / "stremio_account.json"
        ),
        help="Ignored JSON file containing a Stremio auth_key",
    )
    parser.add_argument(
        "--stremio-local-media-root",
        action="append",
        default=[],
        help="Allowed root for local files returned by Stremio Service (repeatable)",
    )
    parser.add_argument("--open-media-addon-port", type=int, default=8756)
    parser.add_argument("--disable-open-media-addon", action="store_true")
    parser.add_argument(
        "--ffprobe",
        default=os.environ.get("POCKETSTREMIO_FFPROBE", ""),
        help="Optional ffprobe executable used for media preflight",
    )
    parser.add_argument(
        "--ffmpeg",
        default=os.environ.get("POCKETSTREMIO_FFMPEG", ""),
        help="Optional ffmpeg executable used for bounded conversion",
    )
    parser.add_argument(
        "--enable-field-test",
        action="store_true",
        help="Enable the app-local embedded-subtitle field-test route",
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
    service_roots = args.stremio_local_media_root or [str(media_dir)]
    httpd.stremio_service = stremio_service.StremioServiceBackend(
        args.stremio_service_url,
        service_roots,
    )
    httpd.stremio_account = stremio_account.StremioAccountBackend(
        args.stremio_account_config
    )
    httpd.stremio_link = link_stremio_account.AccountLinkManager(
        args.stremio_account_config
    )
    httpd.stream_addons = load_stream_addons(args.stream_addons)
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
    httpd.hls_bridge_lock = threading.Lock()
    httpd.active_hls_bridges = 0
    httpd.manifest_cache = {}
    httpd.probe_cache = ProbeCache(
        data_dir / "probe_cache.json", args.probe_cache_ttl, args.max_probe_cache
    )
    httpd.ffprobe_path = playback_compatibility.resolve_ffprobe(args.ffprobe)
    httpd.ffmpeg_path = transcoding.resolve_ffmpeg(args.ffmpeg)
    httpd.field_test_enabled = args.enable_field_test
    httpd.transcode_dir = data_dir / "transcode"
    httpd.transcode_dir.mkdir(parents=True, exist_ok=True)
    for stale_path in httpd.transcode_dir.glob("subtitle-*"):
        stale_path.unlink(missing_ok=True)
    httpd.transcode_job_lock = threading.Lock()
    httpd.transcode_state_lock = threading.Lock()
    httpd.active_transcodes = 0
    httpd.probe_timeout = max(1, args.probe_timeout)
    httpd.progress_store = ProgressStore(data_dir / "continue_watching.json")
    httpd.started_at = time.time()
    httpd.daemon_threads = True

    print(f"PocketStremio server listening on http://{args.host}:{args.port}", flush=True)
    print(f"Public host: {httpd.public_host}", flush=True)
    print(f"Stream addons configured: {len(httpd.stream_addons)}", flush=True)
    print(
        "Stremio Service backend: "
        + (httpd.stremio_service.base_url or "disabled"),
        flush=True,
    )
    print(
        "Stremio local media roots: "
        + ", ".join(str(root) for root in httpd.stremio_service.allowed_roots),
        flush=True,
    )
    print(
        "Stremio account: "
        + (
            "configured"
            if httpd.stremio_account.status()["configured"]
            else "not configured"
        ),
        flush=True,
    )
    print(f"Media preflight: {httpd.ffprobe_path or 'disabled'}", flush=True)
    print(f"Bounded conversion: {httpd.ffmpeg_path or 'disabled'}", flush=True)
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
