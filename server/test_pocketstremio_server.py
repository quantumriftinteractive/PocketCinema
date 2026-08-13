import json
import tempfile
import threading
import unittest
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from server import open_media_addon
from server import pocketstremio_server as pocket


class RedirectingMediaHandler(BaseHTTPRequestHandler):
    content = bytes(range(256)) * 8

    def do_GET(self):
        if self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/video.mp4")
            self.end_headers()
            return

        if self.path != "/video.mp4":
            self.send_response(404)
            self.end_headers()
            return

        range_header = self.headers.get("Range", "")
        if range_header.startswith("bytes="):
            start_text, _, end_text = range_header[6:].partition("-")
            start = int(start_text)
            end = min(int(end_text), len(self.content) - 1)
            body = self.content[start : end + 1]
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{end}/{len(self.content)}")
        else:
            body = self.content
            self.send_response(200)
        self.send_header("Content-Type", "video/mp4")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass


class PocketStremioServerTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        media_dir = root / "media"
        fixture_dir = root / "fixtures"
        media_dir.mkdir()
        fixture_dir.mkdir()
        (media_dir / "test-video.mp4").write_bytes(bytes(range(256)) * 8)
        (fixture_dir / "test-subtitle.srt").write_text(
            "1\n00:00:00,500 --> 00:00:04,500\nTest subtitle\n",
            encoding="utf-8",
        )

        self.server = pocket.ThreadingHTTPServer(
            ("127.0.0.1", 0), pocket.PocketStremioHandler
        )
        self.server.media_dir = media_dir
        self.server.fixture_dir = fixture_dir
        self.server.public_host = "127.0.0.1"
        self.server.server_port = self.server.server_address[1]
        self.server.stream_addons = []
        self.server.stream_cache = {}
        self.server.subtitle_cache = {}
        self.server.play_sessions = {}
        self.server.manifest_cache = {}
        self.server.progress_store = pocket.ProgressStore(
            root / "data" / "continue_watching.json"
        )
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.temp_dir.cleanup()

    def get_json(self, path):
        with urllib.request.urlopen(self.base + path, timeout=5) as response:
            return response.status, json.load(response)

    def post_json(self, path, payload):
        request = urllib.request.Request(
            self.base + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.load(response)

    def test_search_and_meta_are_normalized(self):
        def fake_fetch(url, timeout=pocket.DEFAULT_TIMEOUT):
            del timeout
            if "/catalog/" in url:
                return {
                    "metas": [
                        {
                            "id": "tt0078748",
                            "type": "movie",
                            "name": "Alien",
                            "releaseInfo": "1979",
                        }
                    ]
                }
            return {
                "meta": {
                    "id": "tt0078748",
                    "type": "movie",
                    "name": "Alien",
                    "releaseInfo": "1979",
                    "description": "Test description",
                }
            }

        with mock.patch.object(pocket, "fetch_json", side_effect=fake_fetch):
            status, search = self.get_json("/api/search?q=alien")
            self.assertEqual(status, 200)
            self.assertEqual(search["items"][0]["title"], "Alien")
            status, meta = self.get_json("/api/meta/movie/tt0078748")
            self.assertEqual(status, 200)
            self.assertEqual(meta["year"], 1979)

    def test_play_and_subtitle_proxies_hide_upstream_urls(self):
        _, streams = self.get_json("/api/streams/movie/tt1254207")
        stream = streams["items"][0]
        self.assertNotIn("url", stream)

        _, subtitles = self.get_json(
            f"/api/subtitles/movie/tt1254207?stream_id={stream['id']}"
        )
        subtitle = subtitles["items"][0]
        self.assertNotIn("url", subtitle)
        with urllib.request.urlopen(
            f"{self.base}/subtitle/{subtitle['id']}", timeout=5
        ) as response:
            self.assertIn(b"Test subtitle", response.read())

        _, play = self.post_json(
            "/api/play",
            {"type": "movie", "id": "tt1254207", "stream_id": stream["id"]},
        )
        request = urllib.request.Request(
            play["url"], headers={"Range": "bytes=10-19"}
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            self.assertEqual(response.status, 206)
            self.assertEqual(len(response.read()), 10)

    def test_configured_addon_subtitle_is_normalized(self):
        self.server.stream_addons = [
            {
                "name": "Test subtitles",
                "manifest_url": "https://addon.example/manifest.json",
            }
        ]
        upstream_url = "https://cdn.example/subtitle.srt"
        with mock.patch.object(
            pocket,
            "fetch_json",
            return_value={
                "subtitles": [
                    {"url": upstream_url, "lang": "eng", "name": "English"}
                ]
            },
        ):
            _, subtitles = self.get_json("/api/subtitles/movie/tt0078748")
        self.assertEqual(subtitles["count"], 1)
        subtitle = subtitles["items"][0]
        self.assertEqual(subtitle["lang"], "eng")
        self.assertNotIn("url", subtitle)
        self.assertEqual(
            self.server.subtitle_cache[subtitle["id"]]["url"], upstream_url
        )

    def test_open_media_addon_resolves_opaque_real_stream(self):
        addon = open_media_addon.create_server("127.0.0.1", 0)
        addon_thread = threading.Thread(target=addon.serve_forever, daemon=True)
        addon_thread.start()
        manifest_url = f"http://127.0.0.1:{addon.server_address[1]}/manifest.json"
        self.server.stream_addons = [
            {"name": "PocketStremio Open Media", "manifest_url": manifest_url}
        ]
        try:
            with urllib.request.urlopen(manifest_url, timeout=5) as response:
                manifest = json.load(response)
            self.assertIn("stream", manifest["resources"])

            _, streams = self.get_json("/api/streams/movie/tt0063350")
            self.assertEqual(streams["count"], 1)
            stream = streams["items"][0]
            self.assertEqual(stream["name"], "Open Media - Internet Archive")
            self.assertEqual(stream["duration_seconds"], 5752)
            self.assertNotIn("url", stream)
            self.assertNotIn("source", stream)
            self.assertEqual(
                self.server.stream_cache[stream["id"]]["url"],
                open_media_addon.NIGHT_OF_THE_LIVING_DEAD_URL,
            )
        finally:
            addon.shutdown()
            addon.server_close()
            addon_thread.join(timeout=5)

    def test_play_proxy_preserves_range_across_redirect(self):
        upstream = ThreadingHTTPServer(("127.0.0.1", 0), RedirectingMediaHandler)
        upstream_thread = threading.Thread(target=upstream.serve_forever, daemon=True)
        upstream_thread.start()
        stream_id = "redirect-test"
        self.server.stream_cache[stream_id] = {
            "id": stream_id,
            "name": "Redirect test",
            "url": f"http://127.0.0.1:{upstream.server_address[1]}/redirect",
        }
        try:
            _, play = self.post_json("/api/play", {"stream_id": stream_id})
            request = urllib.request.Request(
                play["url"], headers={"Range": "bytes=100-199"}
            )
            with urllib.request.urlopen(request, timeout=5) as response:
                self.assertEqual(response.status, 206)
                self.assertEqual(response.headers["Content-Type"], "video/mp4")
                self.assertEqual(response.headers["Content-Range"], "bytes 100-199/2048")
                self.assertEqual(response.read(), RedirectingMediaHandler.content[100:200])
        finally:
            upstream.shutdown()
            upstream.server_close()
            upstream_thread.join(timeout=5)

    def test_continue_watching_persists_and_completed_item_is_removed(self):
        payload = {
            "type": "movie",
            "id": "tt1254207",
            "title": "Big Buck Bunny",
            "year": 2008,
            "position_seconds": 2,
            "duration_seconds": 6,
        }
        _, saved = self.post_json("/api/progress", payload)
        self.assertTrue(saved["saved"])
        _, listing = self.get_json("/api/continue-watching")
        self.assertEqual(listing["items"][0]["position_seconds"], 2)

        reloaded = pocket.ProgressStore(self.server.progress_store.path)
        self.assertEqual(reloaded.list_items()[0]["id"], "tt1254207")

        payload["position_seconds"] = 6
        _, completed = self.post_json("/api/progress", payload)
        self.assertFalse(completed["saved"])
        _, listing = self.get_json("/api/continue-watching")
        self.assertEqual(listing["count"], 0)


if __name__ == "__main__":
    unittest.main()
