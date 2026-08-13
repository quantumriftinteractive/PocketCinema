import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from server import open_media_addon
from server import playback_compatibility
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
        self.server.play_sessions = pocket.SessionStore()
        self.server.manifest_cache = {}
        self.server.probe_cache = pocket.ProbeCache(root / "data" / "probe_cache.json")
        self.server.ffprobe_path = ""
        self.server.probe_timeout = 5
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

    def post_json_error(self, path, payload):
        request = urllib.request.Request(
            self.base + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(request, timeout=5)
        return caught.exception.code, json.load(caught.exception)

    def test_search_and_meta_are_normalized(self):
        def fake_fetch(url, timeout=pocket.DEFAULT_TIMEOUT):
            del timeout
            if "/catalog/movie/" in url:
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
            if "/catalog/series/" in url:
                return {
                    "metas": [
                        {
                            "id": "tt9999999",
                            "type": "series",
                            "name": "Alien Test Series",
                            "releaseInfo": "2026",
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
            self.assertEqual(search["items"][1]["type"], "series")
            status, meta = self.get_json("/api/meta/movie/tt0078748")
            self.assertEqual(status, 200)
            self.assertEqual(meta["year"], 1979)

    def test_offline_series_fixture_browses_and_plays_without_upstream(self):
        (self.server.media_dir / "series-av-sync.mp4").write_bytes(
            bytes(range(256)) * 16
        )
        with mock.patch.object(
            pocket,
            "fetch_json",
            side_effect=AssertionError("offline series fixture used an upstream"),
        ):
            status, search = self.get_json("/api/search?q=pocketstremio%20test%20series")
            self.assertEqual(status, 200)
            self.assertEqual(search["count"], 1)
            series = search["items"][0]
            self.assertEqual(series["id"], pocket.TEST_SERIES_ID)
            self.assertEqual(series["type"], "series")
            self.assertNotIn("episodes", series)

            _, meta = self.get_json(f"/api/meta/series/{pocket.TEST_SERIES_ID}")
            self.assertEqual(meta["seasons"], [
                {"number": 1, "episode_count": 3},
                {"number": 2, "episode_count": 2},
            ])
            self.assertEqual(len(meta["episodes"]), 5)
            episode = meta["episodes"][3]
            self.assertEqual(episode["id"], f"{pocket.TEST_SERIES_ID}:2:1")

            _, episode_meta = self.get_json(
                f"/api/meta/series/{episode['id']}"
            )
            self.assertEqual(episode_meta["series_id"], pocket.TEST_SERIES_ID)
            self.assertEqual(episode_meta["season"], 2)
            self.assertEqual(episode_meta["episode"], 1)

            _, streams = self.get_json(f"/api/streams/series/{episode['id']}")
            self.assertEqual(streams["count"], 1)
            stream = streams["items"][0]
            self.assertTrue(stream["playable"])
            self.assertEqual(stream["name"], "Offline episode A/V sync test")
            self.assertEqual(stream["duration_seconds"], 30)
            self.assertEqual(stream["compatibility"]["status"], "confirmed")
            self.assertNotIn("url", stream)

            _, play = self.post_json(
                "/api/play",
                {
                    "type": "series",
                    "id": episode["id"],
                    "stream_id": stream["id"],
                },
            )
            request = urllib.request.Request(
                play["url"], headers={"Range": "bytes=20-39"}
            )
            with urllib.request.urlopen(request, timeout=5) as response:
                self.assertEqual(response.status, 206)
                self.assertEqual(len(response.read()), 20)

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

    def test_optional_compatibility_fixtures_are_allowlisted_and_opaque(self):
        vp8_path = self.server.media_dir / "compat-vp8-vorbis.webm"
        opus_path = self.server.media_dir / "compat-h264-opus.mkv"
        vp8_path.write_bytes(bytes(range(128)) * 4)
        opus_path.write_bytes(bytes(range(128)) * 4)

        _, streams = self.get_json("/api/streams/movie/tt1254207")
        fixtures = {item["id"]: item for item in streams["items"]}
        self.assertEqual(streams["count"], 3)
        self.assertEqual(
            fixtures["fixture-compat-vp8-vorbis"]["compatibility"]["status"],
            "confirmed",
        )
        self.assertNotIn("url", fixtures["fixture-compat-vp8-vorbis"])

        request = urllib.request.Request(
            f"{self.base}/media/compatibility/{vp8_path.name}",
            headers={"Range": "bytes=10-19"},
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            self.assertEqual(response.status, 206)
            self.assertEqual(response.read(), vp8_path.read_bytes()[10:20])

        with self.assertRaises(urllib.error.HTTPError) as rejected:
            urllib.request.urlopen(
                f"{self.base}/media/compatibility/not-allowlisted.mp4",
                timeout=5,
            )
        self.assertEqual(rejected.exception.code, 404)

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

    def test_declared_unsupported_stream_is_hidden_with_reason(self):
        self.server.stream_addons = [
            {
                "name": "Unsupported source",
                "manifest_url": "https://addon.example/manifest.json",
            }
        ]

        def fake_fetch(url, timeout=pocket.DEFAULT_TIMEOUT):
            del timeout
            if url.endswith("manifest.json"):
                return {"resources": ["stream"], "types": ["movie"]}
            return {
                "streams": [
                    {
                        "name": "Unsupported stream",
                        "url": "https://media.example/video.mp4",
                        "behaviorHints": {
                            "pocketstremio": {
                                "status": "unsupported",
                                "message": "AV1 is unsupported",
                            }
                        },
                    }
                ]
            }

        with mock.patch.object(pocket, "fetch_json", side_effect=fake_fetch):
            _, streams = self.get_json("/api/streams/movie/tt0000001")
        self.assertFalse(streams["items"][0]["playable"])
        self.assertEqual(streams["failures"][0]["message"], "AV1 is unsupported")

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

    def test_preflight_classifies_confirmed_and_rejects_unsupported_media(self):
        confirmed_probe = {
            "format": {
                "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
                "duration": "120.5",
                "bit_rate": "800000",
            },
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "profile": "Constrained Baseline",
                    "width": 640,
                    "height": 360,
                    "r_frame_rate": "30/1",
                },
                {
                    "codec_type": "audio",
                    "codec_name": "aac",
                    "sample_rate": "48000",
                    "channels": 2,
                },
            ],
        }
        compatibility = playback_compatibility.classify_probe(confirmed_probe)
        self.assertEqual(compatibility["status"], "confirmed")
        self.assertEqual(compatibility["duration_seconds"], 120)

        confirmed_vp8_probe = {
            "format": {
                "format_name": "matroska,webm",
                "duration": "6.0",
                "bit_rate": "579421",
            },
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "vp8",
                    "width": 640,
                    "height": 360,
                    "r_frame_rate": "30/1",
                },
                {
                    "codec_type": "audio",
                    "codec_name": "vorbis",
                    "sample_rate": "44100",
                    "channels": 2,
                },
            ],
        }
        compatibility = playback_compatibility.classify_probe(confirmed_vp8_probe)
        self.assertEqual(compatibility["status"], "confirmed")
        self.assertIn("VP8/Vorbis", compatibility["message"])

        unsupported_probe = {
            "format": {"format_name": "mov,mp4,m4a,3gp,3g2,mj2"},
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "av1",
                    "width": 640,
                    "height": 360,
                }
            ],
        }
        self.server.ffprobe_path = "test-ffprobe"
        self.server.stream_cache["unsupported"] = {
            "id": "unsupported",
            "name": "Unsupported test",
            "url": "https://media.example/unsupported.mp4",
        }
        with mock.patch.object(
            playback_compatibility, "probe_media", return_value=unsupported_probe
        ) as probe:
            status, error = self.post_json_error(
                "/api/play", {"stream_id": "unsupported"}
            )
        self.assertEqual(status, 409)
        self.assertEqual(error["error"], "unsupported_media")
        self.assertIn("av1", error["message"])
        self.assertEqual(len(self.server.play_sessions), 0)
        probe.assert_called_once()

    def test_preflight_is_cached_and_returned_with_play_session(self):
        self.server.ffprobe_path = "test-ffprobe"
        self.server.stream_cache["candidate"] = {
            "id": "candidate",
            "name": "Candidate test",
            "url": "https://media.example/candidate.webm",
        }
        probe_data = {
            "format": {"format_name": "matroska,webm", "duration": "60"},
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "vp9",
                    "width": 640,
                    "height": 360,
                    "r_frame_rate": "24/1",
                },
                {"codec_type": "audio", "codec_name": "vorbis", "channels": 2},
            ],
        }
        with mock.patch.object(
            playback_compatibility, "probe_media", return_value=probe_data
        ) as probe:
            _, first = self.post_json("/api/play", {"stream_id": "candidate"})
            _, second = self.post_json("/api/play", {"stream_id": "candidate"})
        self.assertEqual(first["compatibility"]["status"], "candidate")
        self.assertEqual(first["duration_seconds"], 60)
        self.assertNotEqual(first["session_id"], second["session_id"])
        probe.assert_called_once()

        cache_text = self.server.probe_cache.path.read_text(encoding="utf-8")
        self.assertNotIn("media.example", cache_text)
        reloaded = pocket.ProbeCache(self.server.probe_cache.path)
        self.assertEqual(
            reloaded.get("https://media.example/candidate.webm")["status"],
            "candidate",
        )

    def test_probe_cache_expires_and_evicts_oldest(self):
        cache = pocket.ProbeCache(
            Path(self.temp_dir.name) / "expiring-probe-cache.json",
            ttl_seconds=10,
            max_items=2,
        )
        with mock.patch.object(pocket.time, "time", return_value=100):
            cache.set("https://media.example/video.mp4", {"status": "confirmed"})
        with mock.patch.object(pocket.time, "time", return_value=101):
            cache.set("https://media.example/second.mp4", {"status": "candidate"})
        with mock.patch.object(pocket.time, "time", return_value=102):
            cache.set("https://media.example/third.mp4", {"status": "candidate"})
            self.assertIsNone(cache.get("https://media.example/video.mp4"))
        with mock.patch.object(pocket.time, "time", return_value=109):
            self.assertEqual(
                cache.get("https://media.example/second.mp4")["status"],
                "candidate",
            )
        with mock.patch.object(pocket.time, "time", return_value=111):
            self.assertIsNone(cache.get("https://media.example/second.mp4"))

    def test_session_store_expires_and_evicts_oldest_sessions(self):
        store = pocket.SessionStore(ttl_seconds=10, max_items=2)
        with mock.patch.object(pocket.time, "time", return_value=100):
            first = store.create({"url": "https://media.example/one"})
        with mock.patch.object(pocket.time, "time", return_value=101):
            second = store.create({"url": "https://media.example/two"})
        with mock.patch.object(pocket.time, "time", return_value=102):
            third = store.create({"url": "https://media.example/three"})
            self.assertEqual(store.get(first), (None, False))
            self.assertIsNotNone(store.get(second)[0])
            self.assertIsNotNone(store.get(third)[0])
        with mock.patch.object(pocket.time, "time", return_value=112):
            self.assertEqual(store.get(second), (None, True))

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
