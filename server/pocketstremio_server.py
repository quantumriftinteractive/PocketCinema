#!/usr/bin/env python3
import argparse
import hashlib
import json
import mimetypes
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


CINEMETA_BASE = "https://v3-cinemeta.strem.io"
DEFAULT_TIMEOUT = 15
BIG_BUCK_BUNNY_ID = "tt1254207"
MAX_CONTINUE_ITEMS = 50


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


def normalize_meta(meta):
    release = str(meta.get("releaseInfo") or meta.get("year") or "")
    year = None
    for token in release.replace("-", " ").split():
        if len(token) >= 4 and token[:4].isdigit():
            year = int(token[:4])
            break

    return {
        "id": meta.get("id") or meta.get("imdb_id"),
        "imdb_id": meta.get("imdb_id") or meta.get("id"),
        "type": meta.get("type") or "movie",
        "title": meta.get("name") or meta.get("title") or "",
        "year": year,
        "poster": meta.get("poster") or "",
        "description": meta.get("description") or "",
    }


def stream_label(stream, fallback):
    name = stream.get("name") or stream.get("title") or fallback
    description = stream.get("description") or ""
    if description:
        return f"{name} - {description[:80]}"
    return name


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
    server_version = "PocketStremio/0.3"

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        parts = [part for part in parsed.path.split("/") if part]

        if parsed.path == "/api/status":
            self.write_json(
                {
                    "status": "ok",
                    "service": "pocketstremio-server",
                    "version": "0.3-subtitles-progress-poc",
                    "message": "PocketStremio server is reachable",
                    "stream_addons": len(self.server.stream_addons),
                    "continue_watching": len(self.server.progress_store.list_items()),
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

        session_id = hashlib.sha1(f"{time.time()}:{stream_id}:{url}".encode()).hexdigest()[:16]
        self.server.play_sessions[session_id] = {
            "created_at": time.time(),
            "stream_id": stream_id,
            "url": url,
            "name": stream.get("name", ""),
            "duration_seconds": stream.get("duration_seconds", 0),
        }

        self.write_json(
            {
                "url": f"http://{self.server.public_host}:{self.server.server_port}/play/{session_id}",
                "session_id": session_id,
                "stream_id": stream_id,
                "duration_seconds": stream.get("duration_seconds", 0),
            }
        )

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

        extra = urllib.parse.quote(f"search={query}", safe="=")
        url = f"{CINEMETA_BASE}/catalog/movie/top/{extra}.json"
        try:
            data = fetch_json(url)
            items = [normalize_meta(meta) for meta in data.get("metas", [])[:12]]
            if "bunny" in query.lower() or "big buck" in query.lower():
                bbb = normalize_meta(
                    fetch_json(f"{CINEMETA_BASE}/meta/movie/{BIG_BUCK_BUNNY_ID}.json").get("meta") or {}
                )
                if bbb.get("id") and all(item.get("id") != bbb["id"] for item in items):
                    items.insert(0, bbb)
        except Exception as exc:
            self.write_json({"error": "search_failed", "message": str(exc)}, status=502)
            return

        self.write_json({"query": query, "count": len(items), "items": items, "results": items})

    def handle_meta(self, item_type, item_id):
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

        if item_type == "movie" and item_id == BIG_BUCK_BUNNY_ID:
            test_video = self.server.media_dir / "test-video.mp4"
            stream_url = f"http://{self.server.public_host}:{self.server.server_port}/media/test-video.mp4"
            streams.append(
                {
                    "id": f"sample-{BIG_BUCK_BUNNY_ID}",
                    "name": "PocketStremio hosted test video",
                    "description": "Known-compatible H.264/AAC MP4 hosted by desktop-gaming",
                    "duration_seconds": 6,
                    "playable": test_video.is_file(),
                    "source": "pocketstremio-sample",
                    "url": stream_url if test_video.is_file() else "",
                }
            )

        for addon_index, addon in enumerate(self.server.stream_addons):
            manifest_url = addon["manifest_url"]
            base = addon_base_from_manifest(manifest_url)
            url = f"{base}/stream/{urllib.parse.quote(item_type)}/{urllib.parse.quote(item_id)}.json"
            try:
                data = fetch_json(url)
            except Exception as exc:
                print(f"stream addon failed: {manifest_url}: {exc}", flush=True)
                continue

            for stream_index, raw in enumerate(data.get("streams", [])):
                stream_url = raw.get("url")
                behavior_hints = raw.get("behaviorHints") or {}
                stream_id = f"a{addon_index}-s{stream_index}-{hashlib.sha1((stream_url or repr(raw)).encode()).hexdigest()[:8]}"
                playable = bool(stream_url and stream_url.startswith(("http://", "https://")))
                streams.append(
                    {
                        "id": stream_id,
                        "name": raw.get("name") or raw.get("title") or f"Stream {stream_index + 1}",
                        "description": raw.get("description") or "",
                        "label": stream_label(raw, f"Stream {stream_index + 1}"),
                        "playable": playable,
                        "source": addon.get("name") or manifest_url,
                        "url": stream_url if playable else "",
                        "video_hash": behavior_hints.get("videoHash") or "",
                        "video_size": behavior_hints.get("videoSize") or 0,
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
        self.write_json({"count": len(public_items), "items": public_items})

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
        session = self.server.play_sessions.get(session_id)
        if not session:
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
        headers = {"User-Agent": "PocketStremio/0.1"}
        if self.headers.get("Range"):
            headers["Range"] = self.headers["Range"]

        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT) as resp:
                self.send_response(resp.status)
                for key in ["Content-Type", "Content-Length", "Content-Range", "Accept-Ranges"]:
                    value = resp.headers.get(key)
                    if value:
                        self.send_header(key, value)
                self.end_headers()
                while True:
                    chunk = resp.read(1024 * 256)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
        except urllib.error.HTTPError as exc:
            self.write_json({"error": "upstream_http_error", "status": exc.code}, status=502)
        except Exception as exc:
            self.write_json({"error": "upstream_fetch_failed", "message": str(exc)}, status=502)

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
    httpd.stream_cache = {}
    httpd.subtitle_cache = {}
    httpd.play_sessions = {}
    httpd.progress_store = ProgressStore(data_dir / "continue_watching.json")

    print(f"PocketStremio server listening on http://{args.host}:{args.port}", flush=True)
    print(f"Public host: {httpd.public_host}", flush=True)
    print(f"Stream addons configured: {len(httpd.stream_addons)}", flush=True)
    print(f"Media directory: {media_dir}", flush=True)
    print(f"Data directory: {data_dir}", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
