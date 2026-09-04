import collections
import io
import json
import socket
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from server import hls_relay
from server import discovery
from server import link_stremio_account
from server import open_media_addon
from server import playback_compatibility
from server import pocketcinema_server as pocket
from server import stremio_account
from server import stremio_service
from server import transcoding


class DiscoveryResponderTest(unittest.TestCase):
    def test_instance_id_is_persistent(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "discovery_instance_id"
            first = discovery.load_or_create_instance_id(path)
            second = discovery.load_or_create_instance_id(path)
        self.assertRegex(first, r"^[a-f0-9]{16}$")
        self.assertEqual(first, second)

    def test_responder_returns_one_named_preferred_address(self):
        responder = discovery.DiscoveryResponder(
            "0123456789abcdef",
            "Mac PCServer",
            "Overlay",
            "http://192.0.2.10:8755",
            "test-version",
            port=0,
            bind_host="127.0.0.1",
        ).start()
        client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client.settimeout(2)
        try:
            client.sendto(
                discovery.DISCOVERY_REQUEST,
                ("127.0.0.1", responder.bound_port),
            )
            packet, _ = client.recvfrom(discovery.MAX_PACKET_BYTES)
        finally:
            client.close()
            responder.close()
        self.assertEqual(
            packet.decode("utf-8"),
            "POCKETSTREMIO_PSS_V1\t0123456789abcdef\tMac PCServer\tOverlay\t"
            "http://192.0.2.10:8755\ttest-version\n",
        )

    def test_responder_ignores_unknown_probe(self):
        responder = discovery.DiscoveryResponder(
            "0123456789abcdef",
            "Mac PCServer",
            "LAN",
            "http://192.0.2.20:8755",
            "test-version",
            port=0,
            bind_host="127.0.0.1",
        ).start()
        client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client.settimeout(0.3)
        try:
            client.sendto(b"not-pocketcinema\n", ("127.0.0.1", responder.bound_port))
            with self.assertRaises(socket.timeout):
                client.recvfrom(discovery.MAX_PACKET_BYTES)
        finally:
            client.close()
            responder.close()


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


class HlsMediaHandler(BaseHTTPRequestHandler):
    segment = (b"\x47" + (b"\x00" * 187)) * 3

    def do_GET(self):
        if self.path == "/master.m3u8":
            body = b"""#EXTM3U
#EXT-X-VERSION:3
#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID=\"audio\",DEFAULT=YES,URI=\"/audio.m3u8\"
#EXT-X-STREAM-INF:BANDWIDTH=1494000,RESOLUTION=640x360,FRAME-RATE=25,CODECS=\"mp4a.40.2,avc1.64001E\",AUDIO=\"audio\"
/video360.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=5068000,RESOLUTION=1280x720,FRAME-RATE=25,CODECS=\"mp4a.40.2,avc1.64001F\",AUDIO=\"audio\"
/video720.m3u8
"""
            content_type = "application/vnd.apple.mpegurl"
        elif self.path == "/video360.m3u8":
            body = b"""#EXTM3U
#EXT-X-TARGETDURATION:6
#EXTINF:6,
/segment.ts
#EXT-X-ENDLIST
"""
            content_type = "application/vnd.apple.mpegurl"
        elif self.path == "/audio.m3u8":
            body = b"#EXTM3U\n#EXTINF:6,\n/audio.aac\n"
            content_type = "application/vnd.apple.mpegurl"
        elif self.path in {"/segment.ts", "/audio.aac", "/key.bin", "/init.mp4"}:
            body = self.segment
            content_type = "video/mp2t"
        else:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass


class RefreshingHlsHandler(BaseHTTPRequestHandler):
    lock = threading.Lock()
    playlist_requests = 0
    successful_playlists = 0
    segment_requests = collections.Counter()
    fail_playlist_request = 0
    playlist_failure_status = 503
    fail_segment_once = None
    end_after_generation = 2

    @classmethod
    def reset(
        cls,
        fail_playlist_request=0,
        playlist_failure_status=503,
        fail_segment_once=None,
        end_after_generation=2,
    ):
        with cls.lock:
            cls.playlist_requests = 0
            cls.successful_playlists = 0
            cls.segment_requests = collections.Counter()
            cls.fail_playlist_request = fail_playlist_request
            cls.playlist_failure_status = playlist_failure_status
            cls.fail_segment_once = fail_segment_once
            cls.end_after_generation = end_after_generation

    @staticmethod
    def segment(sequence):
        return (b"\x47" + bytes([sequence % 256]) * 187) * 3

    def do_GET(self):
        if self.path == "/master.m3u8":
            body = b"""#EXTM3U
#EXT-X-STREAM-INF:BANDWIDTH=1200000,RESOLUTION=640x360,FRAME-RATE=25,CODECS=\"mp4a.40.2,avc1.64001E\"
/live.m3u8
"""
            self.write_response(200, "application/vnd.apple.mpegurl", body)
            return
        if self.path == "/live.m3u8":
            with self.lock:
                type(self).playlist_requests += 1
                request_number = type(self).playlist_requests
                if type(self).fail_playlist_request in {-1, request_number}:
                    self.write_response(
                        type(self).playlist_failure_status,
                        "text/plain",
                        b"temporary failure",
                    )
                    return
                type(self).successful_playlists += 1
                generation = type(self).successful_playlists - 1
            sequence = 100 + generation
            lines = [
                "#EXTM3U",
                "#EXT-X-TARGETDURATION:1",
                f"#EXT-X-MEDIA-SEQUENCE:{sequence}",
            ]
            for value in range(sequence, sequence + 3):
                lines.extend(["#EXTINF:1,", f"/segment-{value}.ts"])
            if (
                type(self).end_after_generation is not None
                and generation >= type(self).end_after_generation
            ):
                lines.append("#EXT-X-ENDLIST")
            body = ("\n".join(lines) + "\n").encode("ascii")
            self.write_response(200, "application/vnd.apple.mpegurl", body)
            return
        if self.path.startswith("/segment-") and self.path.endswith(".ts"):
            try:
                sequence = int(self.path[len("/segment-") : -len(".ts")])
            except ValueError:
                self.send_error(404)
                return
            with self.lock:
                type(self).segment_requests[sequence] += 1
                request_number = type(self).segment_requests[sequence]
            if sequence == type(self).fail_segment_once and request_number == 1:
                self.write_response(503, "text/plain", b"temporary failure")
                return
            self.write_response(200, "video/mp2t", self.segment(sequence))
            return
        self.send_error(404)

    def write_response(self, status, content_type, body):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass


class PocketCinemaServerTest(unittest.TestCase):
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
            ("127.0.0.1", 0), pocket.PocketCinemaHandler
        )
        self.server.media_dir = media_dir
        self.server.fixture_dir = fixture_dir
        self.server.public_host = "127.0.0.1"
        self.server.public_hosts = ("127.0.0.1",)
        self.server.server_port = self.server.server_address[1]
        self.server.stream_addons = []
        self.server.stremio_service = stremio_service.StremioServiceBackend("", [])
        self.server.stremio_account = stremio_account.StremioAccountBackend(
            root / "config" / "stremio_account.json"
        )
        self.server.stremio_link = link_stremio_account.AccountLinkManager(
            self.server.stremio_account.config_path
        )
        self.server.stream_cache = {}
        self.server.subtitle_cache = {}
        self.server.play_sessions = pocket.SessionStore()
        self.server.playback_failures = pocket.SessionStore()
        self.server.hls_bridge_lock = threading.Lock()
        self.server.active_hls_bridges = 0
        self.server.manifest_cache = {}
        self.server.stream_list_cache = pocket.StreamListCache()
        self.server.probe_cache = pocket.ProbeCache(root / "data" / "probe_cache.json")
        self.server.ffprobe_path = ""
        self.server.ffmpeg_path = ""
        self.server.subtitle_burn_in_available = True
        self.server.transcode_dir = root / "data" / "transcode"
        self.server.transcode_dir.mkdir(parents=True)
        self.server.transcode_job_lock = threading.Lock()
        self.server.transcode_state_lock = threading.Lock()
        self.server.active_transcodes = 0
        self.server.transcode_resource_monitor = pocket.TranscodeResourceMonitor(
            root / "data" / "transcode-resources.log"
        )
        self.server.probe_timeout = 5
        self.server.progress_store = pocket.ProgressStore(
            root / "data" / "continue_watching.json"
        )
        self.server.started_at = 100
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

    def get_json_with_host(self, path, host):
        request = urllib.request.Request(self.base + path, headers={"Host": host})
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.load(response)

    def post_json_with_host(self, path, payload, host):
        request = urllib.request.Request(
            self.base + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Host": host},
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.load(response)

    def route_test_play_response(self, host):
        source_url = "https://cdn.example/route-test.mp4"
        self.server.stream_cache["route-test"] = {
            "id": "route-test", "url": source_url, "name": "Route test",
        }
        self.server.probe_cache.set(source_url, {
            "status": "confirmed", "container": "mp4", "video_codec": "h264",
            "audio_codec": "aac", "width": 640, "height": 360,
        })
        return self.post_json_with_host(
            "/api/play", {"type": "movie", "id": "tt0000001", "stream_id": "route-test"}, host
        )[1]

    def test_approved_request_host_keeps_fixture_urls_on_that_route(self):
        self.server.public_hosts = ("127.0.0.1", "100.64.10.20")
        payload = self.route_test_play_response(f"100.64.10.20:{self.server.server_port}")
        self.assertTrue(payload["url"].startswith(f"http://100.64.10.20:{self.server.server_port}/"))

    def test_unapproved_host_cannot_change_returned_route(self):
        self.server.public_hosts = ("127.0.0.1", "100.64.10.20")
        payload = self.route_test_play_response(f"unapproved.example:{self.server.server_port}")
        self.assertTrue(payload["url"].startswith(f"http://127.0.0.1:{self.server.server_port}/"))

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

    def test_status_reports_bounded_runtime_state(self):
        with mock.patch.object(pocket.time, "time", return_value=130):
            status_code, status = self.get_json("/api/status")
        self.assertEqual(status_code, 200)
        self.assertEqual(status["status"], "ok")
        self.assertEqual(status["version"], pocket.SERVER_VERSION)
        self.assertEqual(status["uptime_seconds"], 30)
        self.assertEqual(status["sessions"]["active"], 0)
        self.assertEqual(status["live_bridges"]["active"], 0)
        self.assertEqual(
            status["sessions"]["maximum"], self.server.play_sessions.max_items
        )
        self.assertFalse(status["state"]["play_sessions_persistent"])
        self.assertTrue(status["state"]["probe_cache_persistent"])
        self.assertFalse(status["stremio_service"]["configured"])
        self.assertFalse(status["stremio_account"]["configured"])
        self.assertFalse(status["discovery"]["enabled"])
        self.assertTrue(status["transcodes"]["subtitle_burn_in"])

    def test_unconfigured_account_addon_endpoint_is_empty(self):
        _, addons = self.get_json("/api/addons")
        self.assertFalse(addons["configured"])
        self.assertFalse(addons["authenticated"])
        self.assertEqual(addons["count"], 0)

    def test_account_link_endpoint_never_exposes_retrieval_code_or_auth_key(self):
        self.server.stremio_link.start = mock.Mock(
            return_value={
                "state": "waiting",
                "link": "https://link.stremio.com/ABCD",
                "expires_in": 300,
            }
        )
        status, link = self.post_json("/api/account/link", {})
        self.assertEqual(status, 201)
        self.assertEqual(link["state"], "waiting")
        serialized = json.dumps(link)
        self.assertNotIn("auth", serialized.lower())
        self.assertNotIn("private-code", serialized)

        self.server.stremio_link.status = mock.Mock(
            return_value={"state": "connected"}
        )
        status, account = self.get_json("/api/account?poll=1")
        self.assertEqual(status, 200)
        self.assertEqual(account["link"], {"state": "connected"})
        self.assertFalse(account["account"]["configured"])

    def test_account_addon_is_opaque_and_only_direct_http_streams_are_used(self):
        config_path = self.server.stremio_account.config_path
        config_path.parent.mkdir(parents=True)
        config_path.write_text(
            json.dumps({"auth_key": "private-auth-key"}), encoding="utf-8"
        )
        transport_url = "https://account-addon.example/private/manifest.json"
        upstream_url = "https://cdn.example/private-video.mp4?token=private"

        def fake_post(payload):
            self.assertEqual(payload["authKey"], "private-auth-key")
            return {
                "result": {
                    "addons": [
                        {
                            "manifest": {
                                "id": "org.example.account",
                                "version": "1.0.0",
                                "name": "Account Direct Media",
                                "types": ["movie"],
                                "resources": ["stream"],
                            },
                            "transportUrl": transport_url,
                            "flags": {"official": False, "protected": False},
                        }
                    ]
                }
            }

        def fake_fetch(url):
            self.assertEqual(
                url,
                "https://account-addon.example/private/stream/movie/tt0000001.json",
            )
            return {
                "streams": [
                    {
                        "name": "Direct account stream",
                        "description": "private source https://do-not-expose.example/",
                        "url": upstream_url,
                    },
                    {"name": "Torrent", "infoHash": "0123456789abcdef"},
                    {
                        "name": "External player",
                        "externalUrl": "https://external.example/watch",
                    },
                    {"name": "Private host", "url": "http://127.0.0.1/video.mp4"},
                    {
                        "name": "[RD+] Debrid\n360p",
                        "url": "https://cdn.example/debrid.mp4",
                        "behaviorHints": {
                            "filename": "Show.S01E04.720p.WEB-DL.H264-NTb.mkv"
                        },
                    },
                ]
            }

        self.server.stremio_account._post_json = mock.Mock(side_effect=fake_post)
        self.server.stremio_account._fetch_json = mock.Mock(side_effect=fake_fetch)

        _, addons = self.get_json("/api/addons?refresh=1")
        self.assertTrue(addons["authenticated"])
        self.assertEqual(addons["stream_addons"], 1)
        addons_json = json.dumps(addons)
        self.assertNotIn("private-auth-key", addons_json)
        self.assertNotIn(transport_url, addons_json)

        _, streams = self.get_json("/api/streams/movie/tt0000001")
        self.assertEqual(streams["count"], 2)
        stream = next(
            item for item in streams["items"] if item["name"] == "Direct account stream"
        )
        debrid = next(
            item for item in streams["items"] if item["name"] == "[RD+] Debrid 360p"
        )
        self.assertTrue(all("\n" not in item["name"] for item in streams["items"]))
        self.assertEqual(stream["name"], "Direct account stream")
        self.assertEqual(stream["description"], "")
        self.assertEqual(
            debrid["release_label"], "S01E04 720P WEB-DL H264 NTb"
        )
        self.assertNotIn("url", stream)
        self.assertTrue(
            any("non-HTTP" in failure["message"] for failure in streams["failures"])
        )
        internal = self.server.stream_cache[stream["id"]]
        self.assertEqual(internal["url"], upstream_url)
        self.assertEqual(
            self.server.stream_cache[debrid["id"]]["url"],
            "https://cdn.example/debrid.mp4",
        )

        _, play = self.post_json("/api/play", {"stream_id": stream["id"]})
        public_json = json.dumps({"addons": addons, "streams": streams, "play": play})
        self.assertNotIn("private-auth-key", public_json)
        self.assertNotIn(transport_url, public_json)
        self.assertNotIn(upstream_url, public_json)
        self.assertNotIn("https://cdn.example/debrid.mp4", public_json)
        self.assertNotIn("do-not-expose.example", public_json)

        _, status = self.get_json("/api/status")
        self.assertTrue(status["stremio_account"]["authenticated"])
        self.assertEqual(status["stremio_account"]["stream_addons"], 1)

    def test_account_streams_put_lower_advertised_quality_first(self):
        streams = [
            {"source": "Stremio account: test", "name": "Result 4k"},
            {"source": "Stremio account: test", "name": "Result 720p"},
            {"source": "Stremio account: test", "name": "Result 360p"},
            {"source": "local", "name": "Local fixture"},
        ]
        streams.sort(key=pocket.account_stream_quality_rank)
        self.assertEqual(
            [stream["name"] for stream in streams],
            ["Local fixture", "Result 360p", "Result 720p", "Result 4k"],
        )

    def test_live_tv_catalog_is_account_backed_and_opaque(self):
        private_source = {
            "name": "Greek TV",
            "transport_url": "https://private-addon.example/manifest.json",
        }
        self.server.stremio_account.catalog_sources = mock.Mock(
            return_value=[
                {"source": private_source, "id": "GreekTV", "name": "Greek TV"}
            ]
        )
        self.server.stremio_account.fetch_catalog = mock.Mock(
            return_value=[
                {"id": "grtv_ERTNews_gr", "type": "tv", "name": "ERT News"}
            ]
        )
        _, listing = self.get_json("/api/live-tv")
        self.assertEqual(listing["count"], 1)
        self.assertEqual(listing["items"][0]["title"], "ERT News")
        self.assertEqual(listing["items"][0]["type"], "tv")
        self.assertNotIn("private-addon", json.dumps(listing))

    def test_status_reports_bounded_stremio_service_diagnostics(self):
        backend = stremio_service.StremioServiceBackend(
            "http://127.0.0.1:11470", [self.server.media_dir]
        )

        def fake_fetch(path):
            if path == "/settings":
                return {
                    "values": {
                        "serverVersion": "4.20.8",
                        "localAddonEnabled": True,
                    },
                    "baseUrl": "http://private-address:11470",
                }
            return {
                "id": "org.stremio.local",
                "version": "1.10.0",
                "resources": ["meta", "stream"],
                "types": ["movie", "series"],
            }

        backend._fetch_json = mock.Mock(side_effect=fake_fetch)
        self.server.stremio_service = backend
        _, status = self.get_json("/api/status")
        diagnostics = status["stremio_service"]
        self.assertTrue(diagnostics["reachable"])
        self.assertEqual(diagnostics["version"], "4.20.8")
        self.assertTrue(diagnostics["local_addon_enabled"])
        self.assertTrue(diagnostics["local_addon"]["stream_capable"])
        self.assertNotIn("baseUrl", json.dumps(diagnostics))

    def test_status_reports_stremio_service_unavailable_without_details(self):
        backend = stremio_service.StremioServiceBackend(
            "http://127.0.0.1:11470", [self.server.media_dir]
        )
        backend._fetch_json = mock.Mock(side_effect=OSError("private failure"))
        self.server.stremio_service = backend
        _, status = self.get_json("/api/status")
        diagnostics = status["stremio_service"]
        self.assertFalse(diagnostics["reachable"])
        self.assertEqual(diagnostics["message"], "Stremio Service is unavailable")
        self.assertNotIn("private failure", json.dumps(diagnostics))

    def test_stremio_service_local_file_is_opaque_and_range_playable(self):
        backend = stremio_service.StremioServiceBackend(
            "http://127.0.0.1:11470", [self.server.media_dir]
        )
        local_path = self.server.media_dir / "test-video.mp4"

        def fake_fetch(path):
            if path == "/local-addon/manifest.json":
                return {
                    "id": "org.stremio.local",
                    "resources": ["stream"],
                    "types": ["movie", "series"],
                }
            if path == "/local-addon/stream/movie/tt1254207.json":
                return {
                    "streams": [
                        {
                            "name": "Stremio local fixture",
                            "url": "file://" + str(local_path),
                        }
                    ]
                }
            raise AssertionError(path)

        backend._fetch_json = mock.Mock(side_effect=fake_fetch)
        self.server.stremio_service = backend
        _, streams = self.get_json("/api/streams/movie/tt1254207")
        service_stream = next(
            item for item in streams["items"] if item["name"] == "Stremio local fixture"
        )
        serialized = json.dumps(service_stream)
        self.assertNotIn("url", service_stream)
        self.assertNotIn(str(local_path), serialized)
        cached = self.server.stream_cache[service_stream["id"]]
        self.assertEqual(cached["local_path"], str(local_path.resolve()))

        _, play = self.post_json("/api/play", {"stream_id": service_stream["id"]})
        request = urllib.request.Request(
            play["url"], headers={"Range": "bytes=20-39"}
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            self.assertEqual(response.status, 206)
            self.assertEqual(response.read(), local_path.read_bytes()[20:40])

    def test_stremio_service_rejects_files_outside_allowed_roots(self):
        backend = stremio_service.StremioServiceBackend(
            "http://127.0.0.1:11470", [self.server.media_dir]
        )
        outside_path = self.server.fixture_dir / "test-subtitle.srt"

        def fake_fetch(path):
            if path == "/local-addon/manifest.json":
                return {
                    "resources": ["stream"],
                    "types": ["movie"],
                }
            return {"streams": [{"url": outside_path.as_uri()}]}

        backend._fetch_json = mock.Mock(side_effect=fake_fetch)
        self.server.stremio_service = backend
        _, streams = self.get_json("/api/streams/movie/tt0000001")
        self.assertEqual(streams["count"], 0)
        self.assertEqual(
            streams["failures"][0]["message"],
            "Stremio Service returned no allowed direct local files",
        )

    def test_stremio_service_rechecks_local_file_when_session_is_served(self):
        local_path = self.server.media_dir / "test-video.mp4"
        stream_id = "stale-local-file"
        self.server.stremio_service = stremio_service.StremioServiceBackend(
            "http://127.0.0.1:11470", [self.server.media_dir]
        )
        self.server.stream_cache[stream_id] = {
            "id": stream_id,
            "name": "Local fixture",
            "local_path": str(local_path),
        }
        _, play = self.post_json("/api/play", {"stream_id": stream_id})
        local_path.unlink()
        with self.assertRaises(urllib.error.HTTPError) as rejected:
            urllib.request.urlopen(play["url"], timeout=5)
        self.assertEqual(rejected.exception.code, 404)
        self.assertEqual(json.load(rejected.exception)["error"], "local_media_unavailable")

    def test_stremio_service_url_may_be_a_pcserver_only_remote_origin(self):
        backend = stremio_service.StremioServiceBackend(
            "http://192.0.2.55:11470", [self.server.media_dir]
        )
        self.assertEqual(backend.base_url, "http://192.0.2.55:11470")
        with self.assertRaisesRegex(ValueError, "HTTP origin"):
            stremio_service.StremioServiceBackend(
                "https://user:secret@example.test/service", [self.server.media_dir]
            )

    def test_real_episode_meta_is_resolved_from_parent_series(self):
        parent_meta = {
            "id": "tt0055662",
            "type": "series",
            "name": "The Beverly Hillbillies",
            "releaseInfo": "1962-1971",
            "description": "Series description",
            "poster": "https://images.example/poster.jpg",
            "videos": [
                {
                    "id": "tt0055662:1:1",
                    "season": 1,
                    "episode": 1,
                    "name": "The Clampetts Strike Oil",
                    "released": "1962-09-26T00:00:00.000Z",
                    "overview": "The Clampetts discover oil.",
                }
            ],
        }
        with mock.patch.object(
            pocket, "fetch_json", return_value={"meta": parent_meta}
        ) as fetch:
            status_code, episode = self.get_json(
                "/api/meta/series/tt0055662:1:1"
            )
        self.assertEqual(status_code, 200)
        self.assertEqual(episode["title"], "The Clampetts Strike Oil")
        self.assertEqual(episode["series_id"], "tt0055662")
        self.assertEqual(episode["series_title"], "The Beverly Hillbillies")
        self.assertEqual(episode["season"], 1)
        self.assertEqual(episode["episode"], 1)
        self.assertEqual(episode["year"], 1962)
        self.assertEqual(episode["description"], "The Clampetts discover oil.")
        self.assertTrue(
            fetch.call_args.args[0].endswith("/meta/series/tt0055662.json")
        )

    def test_offline_series_fixture_browses_and_plays_without_upstream(self):
        (self.server.media_dir / "series-av-sync.mp4").write_bytes(
            bytes(range(256)) * 16
        )
        with mock.patch.object(
            pocket,
            "fetch_json",
            side_effect=AssertionError("offline series fixture used an upstream"),
        ):
            status, search = self.get_json("/api/search?q=pocketcinema%20test%20series")
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

    def test_bounded_transcode_uses_opaque_source_and_cleans_up(self):
        stream_id = "private-transcode"
        upstream_url = "https://cdn.example/video.mp4?token=private"
        self.server.stream_cache[stream_id] = {
            "id": stream_id,
            "name": "Private transcode",
            "url": upstream_url,
        }
        self.server.probe_cache.set(
            upstream_url,
            {
                "status": "confirmed",
                "message": "test",
                "container": "mp4",
                "video_codec": "h264",
                "audio_codec": "aac",
                "width": 640,
                "height": 360,
            },
        )
        subtitle_id = "english-test"
        self.server.subtitle_cache[subtitle_id] = {
            "id": subtitle_id,
            "lang": "eng",
            "item_type": "movie",
            "item_id": "tt0000001",
            "local_path": str(self.server.fixture_dir / "test-subtitle.srt"),
        }
        self.server.ffmpeg_path = "test-ffmpeg"

        _, play = self.post_json(
            "/api/play",
            {
                "type": "movie",
                "id": "tt0000001",
                "stream_id": stream_id,
                "subtitle_id": subtitle_id,
                "resume_seconds": 12,
            },
        )
        self.assertTrue(play["transcoded"])
        self.assertTrue(play["server_seek_applied"])
        self.assertNotIn(upstream_url, json.dumps(play))

        transport = (b"\x47" + b"\x00" * 187) * 6

        class FakeProcess:
            def __init__(self):
                self.stdout = io.BytesIO(transport)
                self.stderr = io.BytesIO()

            def poll(self):
                return 0

            def wait(self, timeout=None):
                del timeout
                return 0

            def terminate(self):
                pass

            def kill(self):
                pass

        with mock.patch.object(
            pocket.subprocess, "Popen", side_effect=lambda *args, **kwargs: FakeProcess()
        ) as popen:
            with urllib.request.urlopen(play["url"], timeout=5) as response:
                self.assertEqual(response.headers["Content-Type"], "video/mp2t")
                self.assertEqual(response.read(), transport)

            with urllib.request.urlopen(
                play["url"] + "?start_seconds=34", timeout=5
            ) as response:
                self.assertEqual(response.headers["Content-Type"], "video/mp2t")
                self.assertEqual(response.read(), transport)

        command = popen.call_args.args[0]
        self.assertIn("-ss", command)
        self.assertIn("34", command)
        self.assertTrue(any("/play/" in value for value in command))
        self.assertNotIn(upstream_url, command)
        self.assertFalse(any("token=private" in value for value in command))
        self.assertEqual(self.server.active_transcodes, 0)
        self.assertEqual(list(self.server.transcode_dir.iterdir()), [])

    def test_transcode_reports_subtitle_download_stage(self):
        stream_id = "subtitle-failure-stream"
        upstream_url = "https://cdn.example/video.mp4?token=private"
        self.server.stream_cache[stream_id] = {
            "id": stream_id,
            "name": "Subtitle failure",
            "url": upstream_url,
        }
        self.server.probe_cache.set(
            upstream_url,
            {
                "status": "confirmed",
                "message": "test",
                "container": "mp4",
                "video_codec": "h264",
                "audio_codec": "aac",
                "width": 640,
                "height": 360,
            },
        )
        subtitle_id = "blocked-subtitle"
        self.server.subtitle_cache[subtitle_id] = {
            "id": subtitle_id,
            "lang": "eng",
            "item_type": "movie",
            "item_id": "tt0000001",
            "local_path": str(self.server.fixture_dir / "blocked.srt"),
        }
        self.server.ffmpeg_path = "test-ffmpeg"

        _, play = self.post_json(
            "/api/play",
            {
                "type": "movie",
                "id": "tt0000001",
                "stream_id": stream_id,
                "subtitle_id": subtitle_id,
            },
        )
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(play["url"], timeout=5)
        self.assertEqual(caught.exception.code, 502)
        self.assertEqual(caught.exception.reason, "Subtitle download failed")
        with caught.exception as response:
            payload = json.load(response)
        self.assertEqual(payload["error"], "subtitle_download_failed")
        self.assertEqual(self.server.active_transcodes, 0)

    def test_controlled_transcode_failure_stages(self):
        stream_id = "controlled-transcode-failure"
        upstream_url = "https://cdn.example/video.mp4?token=private"
        self.server.stream_cache[stream_id] = {
            "id": stream_id,
            "name": "Controlled transcode failure",
            "url": upstream_url,
        }
        self.server.probe_cache.set(
            upstream_url,
            {
                "status": "confirmed",
                "message": "test",
                "container": "mp4",
                "video_codec": "h264",
                "audio_codec": "aac",
                "width": 1280,
                "height": 720,
            },
        )
        self.server.ffmpeg_path = "test-ffmpeg"

        for mode, reason, error in (
            ("subtitle-download", "Subtitle download failed", "subtitle_download_failed"),
            ("conversion-start", "Conversion could not start", "transcode_start_failed"),
        ):
            self.server.test_transcode_failure = mode
            _, play = self.post_json(
                "/api/play",
                {"type": "movie", "id": "tt0000001", "stream_id": stream_id},
            )
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(play["url"], timeout=5)
            self.assertEqual(caught.exception.code, 502)
            self.assertEqual(caught.exception.reason, reason)
            with caught.exception as response:
                payload = json.load(response)
            self.assertEqual(payload["error"], error)
            _, reported = self.get_json(f"/api/play-error/{play['session_id']}")
            self.assertEqual(reported, {"error": error})
            self.assertEqual(self.server.active_transcodes, 0)
        self.server.test_transcode_failure = ""

    def test_subtitle_play_is_rejected_without_burn_in_support(self):
        stream_id = "subtitle-capability-stream"
        upstream_url = "https://cdn.example/video.mp4?token=private"
        self.server.stream_cache[stream_id] = {
            "id": stream_id,
            "name": "Subtitle capability",
            "url": upstream_url,
        }
        self.server.probe_cache.set(
            upstream_url,
            {
                "status": "confirmed",
                "message": "test",
                "container": "mp4",
                "video_codec": "h264",
                "audio_codec": "aac",
                "width": 640,
                "height": 360,
            },
        )
        self.server.subtitle_cache["english-test"] = {
            "id": "english-test",
            "lang": "eng",
            "item_type": "movie",
            "item_id": "tt0000001",
            "local_path": str(self.server.fixture_dir / "test-subtitle.srt"),
        }
        self.server.ffmpeg_path = "test-ffmpeg"
        self.server.subtitle_burn_in_available = False

        status, body = self.post_json_error(
            "/api/play",
            {
                "type": "movie",
                "id": "tt0000001",
                "stream_id": stream_id,
                "subtitle_id": "english-test",
            },
        )
        self.assertEqual(status, 409)
        self.assertEqual(body["error"], "subtitle_burn_in_unavailable")
        self.assertIn("cannot burn subtitles", body["message"])

    def test_external_subtitles_are_hidden_without_burn_in_support(self):
        self.server.subtitle_burn_in_available = False
        self.server.stream_addons = [
            {
                "name": "Test subtitles",
                "manifest_url": "https://addon.example/manifest.json",
            }
        ]
        with mock.patch.object(pocket, "fetch_json") as fetch:
            _, subtitles = self.get_json("/api/subtitles/movie/tt0078748")
        fetch.assert_not_called()
        self.assertEqual(subtitles["count"], 0)
        self.assertEqual(subtitles["items"], [])
        self.assertIn("cannot burn", subtitles["unavailable_reason"])

    def test_matroska_subtitles_are_discoverable_without_burn_in_support(self):
        self.server.subtitle_burn_in_available = False
        self.server.matroska_subtitles_enabled = True
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
        ) as fetch:
            _, subtitles = self.get_json(
                "/api/subtitles/movie/tt0078748?all=1&matroska_subtitles=1"
            )
        fetch.assert_called()
        self.assertEqual(subtitles["count"], 1)
        self.assertEqual(subtitles["items"][0]["lang"], "eng")
        self.assertEqual(
            self.server.subtitle_cache[subtitles["items"][0]["id"]]["url"],
            upstream_url,
        )

    def test_transcode_reports_missing_output_stage(self):
        stream_id = "empty-transcode-stream"
        upstream_url = "https://cdn.example/video.mp4?token=private"
        self.server.stream_cache[stream_id] = {
            "id": stream_id,
            "name": "Empty transcode",
            "url": upstream_url,
        }
        self.server.probe_cache.set(
            upstream_url,
            {
                "status": "candidate",
                "message": "test",
                "container": "mp4",
                "video_codec": "h264",
                "audio_codec": "ac3",
                "width": 1280,
                "height": 528,
            },
        )
        self.server.ffmpeg_path = "test-ffmpeg"

        class EmptyProcess:
            def __init__(self):
                self.stdout = io.BytesIO()
                self.stderr = io.BytesIO(b"safe conversion error\n")

            def poll(self):
                return 1

            def wait(self, timeout=None):
                del timeout
                return 1

            def terminate(self):
                pass

            def kill(self):
                pass

        _, play = self.post_json(
            "/api/play",
            {"type": "movie", "id": "tt0000001", "stream_id": stream_id},
        )
        with mock.patch.object(
            pocket.subprocess, "Popen", side_effect=lambda *args, **kwargs: EmptyProcess()
        ):
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(play["url"], timeout=5)
        self.assertEqual(caught.exception.code, 502)
        self.assertEqual(caught.exception.reason, "Conversion produced no media")
        with caught.exception as response:
            payload = json.load(response)
        self.assertEqual(payload["error"], "transcode_failed")
        self.assertEqual(self.server.active_transcodes, 0)

    def test_transcode_policy_and_command_are_bounded(self):
        self.assertTrue(transcoding.needs_downscale({"width": 1280, "height": 720}))
        self.assertTrue(
            transcoding.needs_downscale(
                {"width": 640, "height": 360, "video_profile": "High 10"}
            )
        )
        self.assertFalse(
            transcoding.conversion_geometry_supported(
                {"width": 1920, "height": 800}
            )
        )
        self.assertTrue(
            transcoding.conversion_geometry_supported(
                {"width": 1280, "height": 536}
            )
        )
        self.assertTrue(
            transcoding.needs_downscale(
                {
                    "container": "matroska",
                    "video_codec": "hevc",
                    "audio_codec": "eac3",
                    "width": 640,
                    "height": 360,
                }
            )
        )
        self.assertFalse(
            transcoding.needs_downscale(
                {"width": 640, "height": 360, "frame_rate": 30}
            )
        )
        self.assertEqual(
            transcoding.playback_mode({"status": "confirmed"}), "direct"
        )
        self.assertEqual(
            transcoding.playback_mode(
                {"status": "candidate", "width": 1280, "height": 720}
            ),
            "convert",
        )
        self.assertEqual(
            transcoding.playback_mode({"status": "candidate"}), "check"
        )
        eac3_probe = {
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "hevc",
                    "width": 1920,
                    "height": 1080,
                    "avg_frame_rate": "24/1",
                },
                {
                    "codec_type": "audio",
                    "codec_name": "eac3",
                    "channels": 6,
                },
            ],
            "format": {"format_name": "matroska", "duration": "120"},
        }
        self.assertEqual(
            playback_compatibility.classify_probe(eac3_probe)["status"],
            "candidate",
        )
        self.assertEqual(
            transcoding.playback_mode({"status": "unsupported"}), "blocked"
        )
        stream = {
            "subtitle_match_text": "Show S01E04 720p WEB x264 season pack",
            "video_hash": "",
        }
        trusted_720p = {
            "title": "Show.S01E04.720p.WEB-DL.H264-NTb",
            "from_trusted": True,
        }
        untrusted_1080p = {
            "title": "Show.S01E04.1080p.WEBRip.x264-ION10",
            "from_trusted": False,
        }
        self.assertLess(
            pocket.subtitle_match_rank(trusted_720p, stream),
            pocket.subtitle_match_rank(untrusted_1080p, stream),
        )
        command = transcoding.build_command(
            "ffmpeg", "http://server/play/opaque", "subtitle.vtt", 20
        )
        serialized = " ".join(command)
        self.assertIn("-re", command)
        self.assertIn("scale=640:360", serialized)
        self.assertIn("subtitles=subtitle.vtt", serialized)
        self.assertIn("setpts=PTS+20/TB", serialized)
        self.assertIn("setpts=PTS-STARTPTS", serialized)
        self.assertIn("libx264", command)
        self.assertIn("mpegts", command)
        self.assertNotIn("https://upstream.example", serialized)
        matroska = transcoding.build_matroska_command(
            "ffmpeg", "http://server/play/opaque", ["one.srt", "two.srt"], 20
        )
        matroska_serialized = " ".join(matroska)
        self.assertIn("matroska", matroska)
        self.assertIn("-map 1:0", matroska_serialized)
        self.assertIn("-map 2:0", matroska_serialized)
        self.assertIn("one.srt", matroska)
        self.assertIn("two.srt", matroska)
        self.assertNotIn("https://upstream.example", matroska_serialized)
        shifted = transcoding.shift_subtitle_payload(
            b"1\n00:05:35,000 --> 00:05:40,000\nhello\n\n",
            335,
        )
        self.assertIn(b"00:00:00,000 --> 00:00:05,000", shifted)
        subtitle_package = transcoding.build_subtitle_matroska_command(
            "ffmpeg", "subtitle.srt", "srt"
        )
        self.assertIn("matroska", subtitle_package)

    def test_opt_in_field_test_embeds_subtitles_and_keeps_urls_opaque(self):
        stream_id = "field-test-stream"
        upstream_url = "https://cdn.example/field-test.mp4?token=private"
        self.server.stream_cache[stream_id] = {
            "id": stream_id,
            "name": "Field test",
            "url": upstream_url,
        }
        self.server.probe_cache.set(
            upstream_url,
            {
                "status": "confirmed",
                "container": "mp4",
                "video_codec": "h264",
                "audio_codec": "aac",
                "width": 640,
                "height": 360,
            },
        )
        for subtitle_id in ("field-one", "field-two"):
            self.server.subtitle_cache[subtitle_id] = {
                "id": subtitle_id,
                "lang": "eng",
                "item_type": "movie",
                "item_id": "tt0000001",
                "local_path": str(self.server.fixture_dir / "test-subtitle.srt"),
            }
        self.server.ffmpeg_path = "test-ffmpeg"
        _, normal_play = self.post_json(
            "/api/play",
            {
                "type": "movie",
                "id": "tt0000001",
                "stream_id": stream_id,
                "subtitle_id": "field-one",
                "field_test": True,
            },
        )
        self.assertFalse(normal_play["field_test"])
        self.server.field_test_enabled = True
        _, play = self.post_json(
            "/api/play",
            {
                "type": "movie",
                "id": "tt0000001",
                "stream_id": stream_id,
                "subtitle_id": "field-one",
                "field_test": True,
            },
        )
        self.assertTrue(play["transcoded"])
        self.assertTrue(play["field_test"])
        self.assertNotIn(upstream_url, json.dumps(play))

        transport = b"\x1a\x45\xdf\xa3" + b"matroska-field-test"

        class FakeProcess:
            def __init__(self):
                self.stdout = io.BytesIO(transport)
                self.stderr = io.BytesIO()

            def poll(self):
                return 0

            def wait(self, timeout=None):
                del timeout
                return 0

            def terminate(self):
                pass

            def kill(self):
                pass

        with mock.patch.object(
            pocket.subprocess, "Popen", return_value=FakeProcess()
        ) as popen:
            with urllib.request.urlopen(play["url"], timeout=5) as response:
                self.assertEqual(response.headers["Content-Type"], "video/x-matroska")
                self.assertEqual(response.read(), transport)
        command = popen.call_args.args[0]
        self.assertIn("matroska", command)
        self.assertNotIn(upstream_url, command)
        self.assertEqual(self.server.active_transcodes, 0)
        self.assertEqual(list(self.server.transcode_dir.iterdir()), [])

    def test_matroska_subtitle_mode_bounds_tracks_and_hides_upstream_url(self):
        stream_id = "matroska-subtitle-stream"
        upstream_url = "https://cdn.example/matroska.mp4?token=private"
        self.server.stream_cache[stream_id] = {
            "id": stream_id, "name": "Matroska test", "url": upstream_url
        }
        self.server.probe_cache.set(
            upstream_url,
            {"status": "confirmed", "container": "mp4", "video_codec": "h264",
             "audio_codec": "aac", "width": 640, "height": 360},
        )
        for index in range(4):
            subtitle_id = f"matroska-{index}"
            self.server.subtitle_cache[subtitle_id] = {
                "id": subtitle_id, "name": f"English {index}", "lang": "eng",
                "item_type": "movie", "item_id": "tt0000001",
                "local_path": str(self.server.fixture_dir / "test-subtitle.srt"),
            }
        self.server.ffmpeg_path = "test-ffmpeg"
        self.server.matroska_subtitles_enabled = True
        _, play = self.post_json(
            "/api/play",
            {"type": "movie", "id": "tt0000001", "stream_id": stream_id,
             "subtitle_id": "none", "matroska_subtitles": True},
        )
        self.assertTrue(play["transcoded"])
        self.assertTrue(play["matroska_subtitles"])
        self.assertEqual(len(play["subtitle_tracks"]), 3)
        self.assertIn("/subtitle-pack/", play["subtitle_pack_url"])
        self.assertNotIn(upstream_url, json.dumps(play))
        session, expired = self.server.play_sessions.get(play["session_id"])
        self.assertFalse(expired)
        self.assertTrue(session["matroska_subtitles"])
        self.assertEqual(len(session["matroska_tracks"]), 3)
        self.assertEqual(
            [track["id"] for track in session["matroska_tracks"]],
            ["matroska-0", "matroska-1", "matroska-2"],
        )
        self.assertEqual(
            session["subtitle_path"],
            str(self.server.fixture_dir / "test-subtitle.srt"),
        )

    def test_matroska_subtitle_mode_reports_when_no_english_tracks_exist(self):
        stream_id = "matroska-no-subtitles"
        upstream_url = "https://cdn.example/no-subtitles.mp4"
        self.server.stream_cache[stream_id] = {
            "id": stream_id, "name": "No subtitles", "url": upstream_url
        }
        self.server.probe_cache.set(
            upstream_url,
            {"status": "confirmed", "container": "mp4", "video_codec": "h264",
             "audio_codec": "aac", "width": 640, "height": 360},
        )
        self.server.subtitle_cache["spanish-only"] = {
            "id": "spanish-only", "name": "Spanish", "lang": "spa",
            "item_type": "movie", "item_id": "tt0000002",
            "local_path": str(self.server.fixture_dir / "test-subtitle.srt"),
        }
        self.server.ffmpeg_path = "test-ffmpeg"
        self.server.matroska_subtitles_enabled = True
        status, error = self.post_json_error(
            "/api/play",
            {"type": "movie", "id": "tt0000002", "stream_id": stream_id,
             "subtitle_id": "none", "matroska_subtitles": True},
        )
        self.assertEqual(status, 409)
        self.assertEqual(error["error"], "subtitles_unavailable")
        self.assertIn("preferred-language subtitles", error["message"])

    def test_matroska_subtitle_mode_selects_bounded_preferred_language_tracks(self):
        stream_id = "matroska-multi-language-stream"
        upstream_url = "https://cdn.example/multi-language.mp4?token=private"
        self.server.stream_cache[stream_id] = {
            "id": stream_id, "name": "Multi-language", "url": upstream_url
        }
        self.server.probe_cache.set(
            upstream_url,
            {"status": "confirmed", "container": "mp4", "video_codec": "h264",
             "audio_codec": "aac", "width": 640, "height": 360},
        )
        for language in ("eng", "ell"):
            for index in range(4):
                subtitle_id = f"{language}-{index}"
                self.server.subtitle_cache[subtitle_id] = {
                    "id": subtitle_id, "name": f"{language} {index}", "lang": language,
                    "item_type": "movie", "item_id": "tt0000003",
                    "local_path": str(self.server.fixture_dir / "test-subtitle.srt"),
                }
        self.server.ffmpeg_path = "test-ffmpeg"
        self.server.matroska_subtitles_enabled = True
        _, play = self.post_json(
            "/api/play",
            {"type": "movie", "id": "tt0000003", "stream_id": stream_id,
             "subtitle_id": "none", "matroska_subtitles": True,
             "subtitle_languages": ["ell", "eng"],
             "max_subtitles_per_language": 2},
        )
        self.assertEqual(
            [(track["lang"], track["id"]) for track in play["subtitle_tracks"]],
            [("ell", "ell-0"), ("ell", "ell-1"), ("eng", "eng-0"), ("eng", "eng-1")],
        )
        self.assertNotIn(upstream_url, json.dumps(play))

        transport = b"\x1a\x45\xdf\xa3" + b"matroska-subtitle-pack"

        class FakeProcess:
            def __init__(self):
                self.stdout = io.BytesIO(transport)
                self.stderr = io.BytesIO()

            def poll(self):
                return 0

            def wait(self, timeout=None):
                del timeout
                return 0

            def terminate(self):
                pass

            def kill(self):
                pass

        with mock.patch.object(
            pocket.subprocess, "Popen", return_value=FakeProcess()
        ):
            with urllib.request.urlopen(play["subtitle_pack_url"], timeout=5) as response:
                self.assertEqual(response.headers["Content-Type"], "video/x-matroska")
                self.assertEqual(response.read(), transport)
        self.assertEqual(list(self.server.transcode_dir.iterdir()), [])

    def test_matroska_subtitle_packaging_supports_six_tracks_and_languages(self):
        command = transcoding.build_subtitles_matroska_command(
            "ffmpeg",
            [(f"{language}-{index}.srt", "srt", f"{language} {index}", language)
             for language in ("eng", "ell") for index in range(3)],
        )
        serialized = " ".join(command)
        self.assertEqual(command.count("-map"), 6)
        self.assertIn("language=eng", serialized)
        self.assertIn("language=ell", serialized)
        self.assertIn("ell-2.srt", command)
        self.assertNotIn("https://", serialized)

    def test_optional_compatibility_fixtures_are_allowlisted_and_opaque(self):
        vp8_path = self.server.media_dir / "compat-vp8-vorbis.webm"
        opus_path = self.server.media_dir / "compat-h264-opus.mkv"
        subtitle_path = self.server.media_dir / "subtitle-switch-fixture.mkv"
        vp8_path.write_bytes(bytes(range(128)) * 4)
        opus_path.write_bytes(bytes(range(128)) * 4)
        subtitle_path.write_bytes(bytes(range(128)) * 4)

        _, streams = self.get_json("/api/streams/movie/tt1254207")
        fixtures = {item["id"]: item for item in streams["items"]}
        self.assertEqual(streams["count"], 4)
        self.assertEqual(
            fixtures["fixture-compat-vp8-vorbis"]["compatibility"]["status"],
            "confirmed",
        )
        self.assertNotIn("url", fixtures["fixture-compat-vp8-vorbis"])
        self.assertEqual(
            fixtures["fixture-subtitle-switch-fixture"]["compatibility"]["status"],
            "candidate",
        )
        self.assertNotIn("url", fixtures["fixture-subtitle-switch-fixture"])

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
            _, subtitles = self.get_json("/api/subtitles/movie/tt0078748?all=1")
        self.assertEqual(subtitles["count"], 1)
        self.assertEqual(subtitles["other_count"], 0)
        subtitle = subtitles["items"][0]
        self.assertEqual(subtitle["lang"], "eng")
        self.assertNotIn("url", subtitle)
        self.assertEqual(
            self.server.subtitle_cache[subtitle["id"]]["url"], upstream_url
        )

    def test_subtitle_languages_are_bounded_normalized_and_ordered(self):
        self.server.stream_addons = [
            {
                "name": "Test subtitles",
                "manifest_url": "https://addon.example/manifest.json",
            }
        ]
        with mock.patch.object(
            pocket,
            "fetch_json",
            return_value={
                "subtitles": [
                    {
                        "url": "https://cdn.example/japanese.srt",
                        "lang": "ja-JP",
                        "name": "Japanese",
                    },
                    {
                        "url": "https://cdn.example/english.srt",
                        "lang": "en-US",
                        "name": "English",
                    },
                    {
                        "url": "https://cdn.example/spanish.srt",
                        "lang": "es",
                        "name": "Spanish",
                    },
                    {
                        "url": "https://cdn.example/greek.srt",
                        "lang": "gre",
                        "name": "Greek",
                    },
                ]
            },
        ):
            _, preferred = self.get_json(
                "/api/subtitles/movie/tt0078748?all=1&languages=jpn,spa,eng"
            )
            _, default = self.get_json("/api/subtitles/movie/tt0078748?all=1")
        self.assertEqual(
            [subtitle["lang"] for subtitle in preferred["items"]],
            ["jpn", "spa", "eng"],
        )
        self.assertEqual(
            [subtitle["lang"] for subtitle in default["items"]], ["eng"]
        )

    def test_language_aliases_cover_name_picker_catalog_conventions(self):
        aliases = {
            "tr-TR": "tur",
            "ja-JP": "jpn",
            "de": "deu",
            "fre": "fra",
            "chi": "zho",
            "pt-BR": "por",
        }
        self.assertEqual(
            {
                raw: playback_compatibility.normalize_language_tag(raw)
                for raw in aliases
            },
            aliases,
        )

    def test_subtitle_default_filters_weak_matches_with_explicit_fallback(self):
        self.server.stream_cache["matched-stream"] = {
            "id": "matched-stream",
            "subtitle_match_text": "Example Show S01E04 720p WEB x264",
        }
        self.server.stream_addons = [
            {
                "name": "Test subtitles",
                "manifest_url": "https://addon.example/manifest.json",
            }
        ]
        with mock.patch.object(
            pocket,
            "fetch_json",
            return_value={
                "subtitles": [
                    {
                        "url": "https://cdn.example/matched.srt",
                        "lang": "eng",
                        "name": "Example.Show.S01E04.720p.WEB.x264",
                    },
                    {
                        "url": "https://cdn.example/unrelated.srt",
                        "lang": "eng",
                        "name": "Different.Show.S02E03.1080p.BluRay",
                    },
                ]
            },
        ):
            _, matched = self.get_json(
                "/api/subtitles/movie/tt0078748?stream_id=matched-stream"
            )
            _, all_subtitles = self.get_json(
                "/api/subtitles/movie/tt0078748?stream_id=matched-stream&all=1"
            )
        self.assertEqual(matched["count"], 1)
        self.assertEqual(matched["other_count"], 1)
        self.assertEqual(all_subtitles["count"], 2)
        self.assertEqual(all_subtitles["other_count"], 0)

    def test_srt_subtitle_normalization_keeps_local_srt(self):
        payload = b"1\n00:00:00,000 --> 00:00:01,000\nPocketCinema\n"
        with tempfile.TemporaryDirectory() as directory:
            path = transcoding.normalize_subtitle_payload(
                "unused-ffmpeg", payload, directory
            )
            self.assertEqual(path.suffix, ".srt")
            self.assertEqual(path.read_bytes(), payload)

    def test_open_media_addon_resolves_opaque_real_stream(self):
        addon = open_media_addon.create_server("127.0.0.1", 0)
        addon_thread = threading.Thread(target=addon.serve_forever, daemon=True)
        addon_thread.start()
        manifest_url = f"http://127.0.0.1:{addon.server_address[1]}/manifest.json"
        self.server.stream_addons = [
            {"name": "PocketCinema Open Media", "manifest_url": manifest_url}
        ]
        try:
            with urllib.request.urlopen(manifest_url, timeout=5) as response:
                manifest = json.load(response)
            self.assertIn("stream", manifest["resources"])
            self.assertEqual(manifest["types"], ["movie", "series"])

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

            _, episode_streams = self.get_json(
                "/api/streams/series/"
                f"{open_media_addon.BEVERLY_HILLBILLIES_S01E01_ID}"
            )
            self.assertEqual(episode_streams["count"], 1)
            episode_stream = episode_streams["items"][0]
            self.assertEqual(
                episode_stream["name"], "Open Media - Internet Archive"
            )
            self.assertEqual(episode_stream["duration_seconds"], 1492)
            self.assertEqual(episode_stream["compatibility"]["status"], "confirmed")
            self.assertNotIn("url", episode_stream)
            self.assertNotIn("source", episode_stream)
            self.assertEqual(
                self.server.stream_cache[episode_stream["id"]]["url"],
                open_media_addon.BEVERLY_HILLBILLIES_S01E01_URL,
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
                            "pocketcinema": {
                                "status": "unsupported",
                                "message": "AV1 is unsupported",
                            }
                        },
                    }
                ]
            }

        with mock.patch.object(pocket, "fetch_json", side_effect=fake_fetch):
            _, streams = self.get_json("/api/streams/movie/tt0000001")
        self.assertEqual(streams["count"], 0)
        self.assertEqual(streams["items"], [])
        self.assertEqual(streams["failures"][0]["message"], "AV1 is unsupported")

    def test_cached_conversion_stream_is_hidden_without_ffmpeg(self):
        stream_id = "conversion-without-ffmpeg"
        stream_url = "https://media.example/too-large.mp4"
        self.server.stream_cache[stream_id] = {
            "id": stream_id,
            "name": "Unused",
            "url": stream_url,
        }
        self.server.stream_addons = [
            {"name": "Test source", "manifest_url": "https://addon.example/manifest.json"}
        ]
        self.server.probe_cache.set(
            stream_url,
            {
                "status": "candidate",
                "message": "requires conversion",
                "container": "mp4",
                "video_codec": "h264",
                "audio_codec": "aac",
                "width": 1280,
                "height": 720,
            },
        )
        self.server.ffmpeg_path = ""

        def fake_fetch(url, timeout=pocket.DEFAULT_TIMEOUT):
            del timeout
            if url.endswith("manifest.json"):
                return {"resources": ["stream"], "types": ["movie"]}
            return {"streams": [{"name": "Large", "url": stream_url}]}

        with mock.patch.object(pocket, "fetch_json", side_effect=fake_fetch):
            _, streams = self.get_json("/api/streams/movie/tt0000001")
        self.assertEqual(streams["count"], 0)
        self.assertEqual(streams["items"], [])

    def test_stream_list_cache_stabilizes_backtracking_without_exposing_urls(self):
        self.server.stream_addons = [
            {
                "name": "Changing source",
                "manifest_url": "https://addon.example/manifest.json",
            }
        ]
        stream_calls = 0

        def fake_fetch(url, timeout=pocket.DEFAULT_TIMEOUT):
            nonlocal stream_calls
            del timeout
            if url.endswith("manifest.json"):
                return {"resources": ["stream"], "types": ["movie"]}
            stream_calls += 1
            return {
                "streams": [
                    {
                        "name": f"Result {stream_calls}",
                        "url": (
                            "https://media.example/"
                            f"result-{stream_calls}.mp4?token=private"
                        ),
                    }
                ]
            }

        with mock.patch.object(pocket, "fetch_json", side_effect=fake_fetch):
            _, first = self.get_json("/api/streams/movie/tt0000001")
            _, second = self.get_json("/api/streams/movie/tt0000001")
        self.assertEqual(stream_calls, 1)
        self.assertEqual(first["items"], second["items"])
        self.assertNotIn("media.example", json.dumps(second))
        self.assertNotIn("token=private", json.dumps(second))

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

    def test_hls_bridge_selects_compatible_variant_and_streams_mpegts(self):
        upstream = ThreadingHTTPServer(("127.0.0.1", 0), HlsMediaHandler)
        upstream_thread = threading.Thread(target=upstream.serve_forever, daemon=True)
        upstream_thread.start()
        upstream_url = f"http://127.0.0.1:{upstream.server_address[1]}/master.m3u8"
        self.server.ffprobe_path = "test-ffprobe"
        self.server.stream_cache["hls-test"] = {
            "id": "hls-test",
            "name": "HLS test",
            "url": upstream_url,
        }
        probe_data = {
            "format": {"format_name": "hls", "bit_rate": "1494000"},
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "profile": "High",
                    "width": 640,
                    "height": 360,
                    "avg_frame_rate": "25/1",
                    "r_frame_rate": "90000/1",
                },
                {"codec_type": "audio", "codec_name": "aac", "channels": 2},
            ],
        }
        try:
            with mock.patch.object(
                playback_compatibility, "probe_media", return_value=probe_data
            ), mock.patch.object(
                stremio_account, "validate_direct_stream_url", return_value=True
            ):
                _, play = self.post_json("/api/play", {"stream_id": "hls-test"})
                self.assertEqual(play["compatibility"]["status"], "candidate")
                self.assertEqual(play["compatibility"]["frame_rate"], 25.0)
                with urllib.request.urlopen(play["url"], timeout=5) as response:
                    self.assertEqual(response.headers["Content-Type"], "video/mp2t")
                    media = response.read()
                self.assertEqual(media, HlsMediaHandler.segment)
                public_json = json.dumps(play)
                self.assertNotIn(upstream_url, public_json)
        finally:
            upstream.shutdown()
            upstream.server_close()
            upstream_thread.join(timeout=5)

    def test_hls_bridge_rejects_encrypted_and_fragmented_playlists(self):
        encrypted = b"""#EXTM3U
#EXT-X-KEY:METHOD=AES-128,URI=\"key.bin\"
#EXTINF:6,
segment.ts
"""
        fragmented = b"""#EXTM3U
#EXT-X-MAP:URI=\"init.mp4\"
#EXTINF:6,
segment.m4s
"""
        byte_range = b"""#EXTM3U
#EXT-X-BYTERANGE:564@0
#EXTINF:6,
segments.ts
"""
        for payload, message in (
            (encrypted, "Encrypted HLS"),
            (fragmented, "Fragmented MP4"),
            (byte_range, "Byte-range HLS"),
        ):
            with self.assertRaisesRegex(hls_relay.HlsRelayError, message):
                hls_relay.parse_media_playlist(
                    payload,
                    "https://media.example/live/index.m3u8",
                    lambda value: value.startswith("https://media.example/"),
                )

    def test_hls_bridge_refreshes_and_deduplicates_overlapping_segments(self):
        RefreshingHlsHandler.reset()
        upstream = ThreadingHTTPServer(("127.0.0.1", 0), RefreshingHlsHandler)
        upstream_thread = threading.Thread(target=upstream.serve_forever, daemon=True)
        upstream_thread.start()
        try:
            play = self.create_refreshing_hls_play(upstream)
            with mock.patch.object(
                stremio_account, "validate_direct_stream_url", return_value=True
            ), mock.patch.object(pocket.time, "sleep"):
                with urllib.request.urlopen(play["url"], timeout=5) as response:
                    body = response.read()
            self.assertEqual(len(body), 5 * 564)
            sequences = [body[offset + 1] for offset in range(0, len(body), 564)]
            self.assertEqual(sequences, [100, 101, 102, 103, 104])
            self.assertEqual(
                dict(RefreshingHlsHandler.segment_requests),
                {100: 1, 101: 1, 102: 1, 103: 1, 104: 1},
            )
        finally:
            upstream.shutdown()
            upstream.server_close()
            upstream_thread.join(timeout=5)

    def test_hls_bridge_recovers_from_one_playlist_http_failure(self):
        RefreshingHlsHandler.reset(fail_playlist_request=2)
        upstream = ThreadingHTTPServer(("127.0.0.1", 0), RefreshingHlsHandler)
        upstream_thread = threading.Thread(target=upstream.serve_forever, daemon=True)
        upstream_thread.start()
        try:
            play = self.create_refreshing_hls_play(upstream)
            with mock.patch.object(
                stremio_account, "validate_direct_stream_url", return_value=True
            ), mock.patch.object(pocket.time, "sleep"):
                with urllib.request.urlopen(play["url"], timeout=5) as response:
                    body = response.read()
            sequences = [body[offset + 1] for offset in range(0, len(body), 564)]
            self.assertEqual(sequences, [100, 101, 102, 103, 104])
            self.assertEqual(RefreshingHlsHandler.playlist_requests, 4)
        finally:
            upstream.shutdown()
            upstream.server_close()
            upstream_thread.join(timeout=5)

    def test_hls_bridge_bounds_persistent_playlist_failure(self):
        RefreshingHlsHandler.reset(fail_playlist_request=-1)
        upstream = ThreadingHTTPServer(("127.0.0.1", 0), RefreshingHlsHandler)
        upstream_thread = threading.Thread(target=upstream.serve_forever, daemon=True)
        upstream_thread.start()
        try:
            play = self.create_refreshing_hls_play(upstream)
            with mock.patch.object(
                stremio_account, "validate_direct_stream_url", return_value=True
            ), mock.patch.object(pocket.time, "sleep"):
                with self.assertRaises(urllib.error.HTTPError) as raised:
                    urllib.request.urlopen(play["url"], timeout=5)
            try:
                self.assertEqual(raised.exception.code, 502)
                error = json.loads(raised.exception.read())
            finally:
                raised.exception.close()
            self.assertEqual(error["error"], "hls_bridge_failed")
            self.assertEqual(
                error["message"], "The live stream is temporarily unavailable"
            )
            self.assertNotIn(str(upstream.server_address[1]), json.dumps(error))
            self.assertEqual(RefreshingHlsHandler.playlist_requests, 3)
            with self.server.hls_bridge_lock:
                self.assertEqual(self.server.active_hls_bridges, 0)
        finally:
            upstream.shutdown()
            upstream.server_close()
            upstream_thread.join(timeout=5)

    def test_hls_bridge_does_not_retry_nontransient_http_failure(self):
        RefreshingHlsHandler.reset(
            fail_playlist_request=-1,
            playlist_failure_status=404,
        )
        upstream = ThreadingHTTPServer(("127.0.0.1", 0), RefreshingHlsHandler)
        upstream_thread = threading.Thread(target=upstream.serve_forever, daemon=True)
        upstream_thread.start()
        try:
            play = self.create_refreshing_hls_play(upstream)
            with mock.patch.object(
                stremio_account, "validate_direct_stream_url", return_value=True
            ), mock.patch.object(pocket.time, "sleep"):
                with self.assertRaises(urllib.error.HTTPError) as raised:
                    urllib.request.urlopen(play["url"], timeout=5)
            raised.exception.close()
            self.assertEqual(raised.exception.code, 502)
            self.assertEqual(RefreshingHlsHandler.playlist_requests, 1)
        finally:
            upstream.shutdown()
            upstream.server_close()
            upstream_thread.join(timeout=5)

    def test_hls_bridge_recovers_before_failed_segment_sends_bytes(self):
        RefreshingHlsHandler.reset(fail_segment_once=103)
        upstream = ThreadingHTTPServer(("127.0.0.1", 0), RefreshingHlsHandler)
        upstream_thread = threading.Thread(target=upstream.serve_forever, daemon=True)
        upstream_thread.start()
        try:
            play = self.create_refreshing_hls_play(upstream)
            with mock.patch.object(
                stremio_account, "validate_direct_stream_url", return_value=True
            ), mock.patch.object(pocket.time, "sleep"):
                with urllib.request.urlopen(play["url"], timeout=5) as response:
                    body = response.read()
            sequences = [body[offset + 1] for offset in range(0, len(body), 564)]
            self.assertEqual(sequences, [100, 101, 102, 103, 104])
            self.assertEqual(RefreshingHlsHandler.segment_requests[103], 2)
        finally:
            upstream.shutdown()
            upstream.server_close()
            upstream_thread.join(timeout=5)

    def test_hls_bridge_stops_after_downstream_disconnect(self):
        RefreshingHlsHandler.reset(end_after_generation=None)
        upstream = ThreadingHTTPServer(("127.0.0.1", 0), RefreshingHlsHandler)
        upstream_thread = threading.Thread(target=upstream.serve_forever, daemon=True)
        upstream_thread.start()
        bridge_started = threading.Event()
        bridge_stopped = threading.Event()
        original_bridge = pocket.PocketCinemaHandler.stream_hls_transport

        def tracked_bridge(handler, session):
            bridge_started.set()
            try:
                return original_bridge(handler, session)
            finally:
                bridge_stopped.set()

        try:
            play = self.create_refreshing_hls_play(upstream)
            with mock.patch.object(
                stremio_account, "validate_direct_stream_url", return_value=True
            ), mock.patch.object(
                pocket.PocketCinemaHandler,
                "stream_hls_transport",
                tracked_bridge,
            ):
                response = urllib.request.urlopen(play["url"], timeout=5)
                self.assertTrue(bridge_started.wait(1))
                with self.server.hls_bridge_lock:
                    self.assertEqual(self.server.active_hls_bridges, 1)
                self.assertEqual(len(response.read(564)), 564)
                response.close()
                self.assertTrue(bridge_stopped.wait(3))
                with self.server.hls_bridge_lock:
                    self.assertEqual(self.server.active_hls_bridges, 0)
        finally:
            upstream.shutdown()
            upstream.server_close()
            upstream_thread.join(timeout=5)

    def create_refreshing_hls_play(self, upstream):
        stream_id = "refreshing-hls"
        self.server.stream_cache[stream_id] = {
            "id": stream_id,
            "name": "Refreshing HLS",
            "url": f"http://127.0.0.1:{upstream.server_address[1]}/master.m3u8",
        }
        self.server.probe_cache.set(
            self.server.stream_cache[stream_id]["url"],
            {
                "status": "candidate",
                "message": "HLS test",
                "container": "hls",
                "video_codec": "h264",
                "audio_codec": "aac",
            },
        )
        with mock.patch.object(
            stremio_account, "validate_direct_stream_url", return_value=True
        ):
            _, play = self.post_json("/api/play", {"stream_id": stream_id})
        return play

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
                    "tags": {"language": "en-US", "title": "English"},
                },
                {
                    "codec_type": "audio",
                    "codec_name": "aac",
                    "sample_rate": "48000",
                    "channels": 2,
                    "tags": {"language": "es", "title": "Spanish"},
                },
            ],
        }
        compatibility = playback_compatibility.classify_probe(confirmed_probe)
        self.assertEqual(compatibility["status"], "confirmed")
        self.assertEqual(compatibility["duration_seconds"], 120)
        self.assertEqual(compatibility["audio_languages"], ["eng", "spa"])
        self.assertEqual(len(compatibility["audio_tracks"]), 2)

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
        self.server.ffmpeg_path = "test-ffmpeg"
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

    def test_corrupt_persistent_state_recovers_without_runtime_failure(self):
        root = Path(self.temp_dir.name) / "corrupt-state"
        root.mkdir()
        probe_path = root / "probe_cache.json"
        progress_path = root / "continue_watching.json"
        probe_path.write_text("{not json", encoding="utf-8")
        progress_path.write_text("[] trailing", encoding="utf-8")

        cache = pocket.ProbeCache(probe_path)
        progress = pocket.ProgressStore(progress_path)
        self.assertEqual(len(cache), 0)
        self.assertEqual(progress.list_items(), [])

        cache.set("https://media.example/recovered.mp4", {"status": "candidate"})
        progress.update(
            {
                "type": "movie",
                "id": "tt0000001",
                "title": "Recovered",
                "position_seconds": 10,
                "duration_seconds": 100,
            }
        )
        self.assertEqual(
            pocket.ProbeCache(probe_path).get(
                "https://media.example/recovered.mp4"
            )["status"],
            "candidate",
        )
        self.assertEqual(
            pocket.ProgressStore(progress_path).list_items()[0]["id"],
            "tt0000001",
        )

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

    def test_continue_watching_removes_only_the_selected_item(self):
        first = {
            "type": "movie",
            "id": "tt1254207",
            "title": "Big Buck Bunny",
            "year": 2008,
            "position_seconds": 2,
            "duration_seconds": 596,
        }
        second = {
            "type": "series",
            "id": "tt0055662:1:1",
            "title": "The Beverly Hillbillies - S1E1",
            "year": 1962,
            "position_seconds": 44,
            "duration_seconds": 1500,
        }
        self.post_json("/api/progress", first)
        self.post_json("/api/progress", second)

        _, removed = self.post_json(
            "/api/continue-watching/remove",
            {"type": first["type"], "id": first["id"]},
        )
        self.assertTrue(removed["removed"])
        _, listing = self.get_json("/api/continue-watching")
        self.assertEqual(listing["count"], 1)
        self.assertEqual(listing["items"][0]["id"], second["id"])

        reloaded = pocket.ProgressStore(self.server.progress_store.path)
        self.assertEqual(
            [item["id"] for item in reloaded.list_items()], [second["id"]]
        )

        _, repeated = self.post_json(
            "/api/continue-watching/remove",
            {"type": first["type"], "id": first["id"]},
        )
        self.assertFalse(repeated["removed"])

    def test_continue_watching_remove_rejects_missing_identity(self):
        status, payload = self.post_json_error(
            "/api/continue-watching/remove", {"type": "movie"}
        )
        self.assertEqual(status, 400)
        self.assertEqual(payload["error"], "invalid_progress")

    def test_continue_watching_repairs_generic_saved_title(self):
        self.post_json(
            "/api/progress",
            {
                "type": "movie",
                "id": "tt16366836",
                "title": "PocketCinema",
                "year": 2024,
                "position_seconds": 155,
                "duration_seconds": 6537,
            },
        )
        with mock.patch.object(
            pocket,
            "fetch_json",
            return_value={"meta": {"id": "tt16366836", "name": "Venom: The Last Dance", "year": 2024}},
        ):
            _, listing = self.get_json("/api/continue-watching")
        self.assertEqual(listing["items"][0]["title"], "Venom: The Last Dance")
        self.assertEqual(listing["items"][0]["position_seconds"], 155)


if __name__ == "__main__":
    unittest.main()
