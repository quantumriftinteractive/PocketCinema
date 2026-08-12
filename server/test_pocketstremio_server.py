import json
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path
from unittest import mock

from server import pocketstremio_server as pocket


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
