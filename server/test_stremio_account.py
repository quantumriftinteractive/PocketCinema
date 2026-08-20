import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from server import link_stremio_account
from server import stremio_account


def descriptor(
    name="Direct Media",
    transport_url="https://addon.example/config/manifest.json",
    p2p=False,
):
    return {
        "manifest": {
            "id": "org.example.direct",
            "version": "1.2.3",
            "name": name,
            "types": ["movie", "series"],
            "resources": ["stream", {"name": "subtitles"}],
            "behaviorHints": {"p2p": p2p},
        },
        "transportUrl": transport_url,
        "flags": {"official": False, "protected": False},
    }


class StremioAccountBackendTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temp_dir.name) / "config" / "account.json"
        self.config_path.parent.mkdir()
        self.config_path.write_text(
            json.dumps({"auth_key": "private-auth-key"}), encoding="utf-8"
        )
        self.backend = stremio_account.StremioAccountBackend(self.config_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_collection_request_and_public_response_are_bounded(self):
        seen = []

        def fake_post(payload):
            seen.append(payload)
            return {
                "result": {
                    "addons": [
                        descriptor(),
                        descriptor(
                            name="P2P source",
                            transport_url="https://p2p.example/manifest.json",
                            p2p=True,
                        ),
                        descriptor(
                            name="Local source",
                            transport_url="http://127.0.0.1:7000/manifest.json",
                        ),
                    ],
                    "lastModified": "2026-08-14T00:00:00Z",
                }
            }

        self.backend._post_json = mock.Mock(side_effect=fake_post)
        public = self.backend.public_collection(force=True)
        self.assertEqual(
            seen,
            [
                {
                    "type": "AddonCollectionGet",
                    "authKey": "private-auth-key",
                    "update": True,
                }
            ],
        )
        self.assertTrue(public["authenticated"])
        self.assertEqual(public["count"], 3)
        self.assertEqual(public["stream_addons"], 1)
        serialized = json.dumps(public)
        self.assertNotIn("private-auth-key", serialized)
        self.assertNotIn("transportUrl", serialized)
        self.assertNotIn("addon.example", serialized)
        self.assertEqual(public["items"][1]["message"], "P2P addon is unsupported")
        self.assertFalse(public["items"][2]["usable"])

    def test_collection_is_cached_and_auth_change_invalidates_cache(self):
        self.backend._post_json = mock.Mock(
            return_value={"result": {"addons": [descriptor()]}}
        )
        self.backend.collection()
        self.backend.collection()
        self.assertEqual(self.backend._post_json.call_count, 1)

        self.config_path.write_text(
            json.dumps({"auth_key": "replacement-key"}), encoding="utf-8"
        )
        self.backend.collection()
        self.assertEqual(self.backend._post_json.call_count, 2)
        self.assertEqual(
            self.backend._post_json.call_args.args[0]["authKey"], "replacement-key"
        )

    def test_expired_session_returns_only_generic_error(self):
        self.backend._post_json = mock.Mock(
            return_value={"error": {"code": 1, "message": "private detail"}}
        )
        with self.assertRaisesRegex(
            stremio_account.StremioAccountError, "session expired"
        ) as caught:
            self.backend.collection(force=True)
        self.assertNotIn("private detail", str(caught.exception))
        self.assertEqual(
            self.backend.status()["message"], "Stremio account session expired"
        )

    def test_transport_and_stream_url_validation(self):
        self.assertTrue(
            stremio_account.validate_transport_url(
                "https://addon.example/config/manifest.json"
            )
        )
        for value in (
            "http://addon.example/manifest.json",
            "https://127.0.0.1/manifest.json",
            "https://10.0.0.1/manifest.json",
            "https://user:pass@addon.example/manifest.json",
            "https://addon.example/not-a-manifest",
        ):
            self.assertFalse(stremio_account.validate_transport_url(value), value)

        self.assertTrue(
            stremio_account.validate_direct_stream_url(
                "https://cdn.example/video.mp4?signature=private"
            )
        )
        for value in (
            "file:///private/video.mp4",
            "http://127.0.0.1/video.mp4",
            "https://192.168.1.2/video.mp4",
            "https://user:pass@cdn.example/video.mp4",
            None,
        ):
            self.assertFalse(stremio_account.validate_direct_stream_url(value), value)

    def test_only_p2p_and_external_stream_shapes_are_rejected(self):
        for value in (
            {"infoHash": "0123456789abcdef"},
            {"externalUrl": "https://external.example/watch"},
            {"ytId": "video-id"},
        ):
            self.assertTrue(stremio_account.has_unsupported_stream_shape(value), value)
        self.assertFalse(
            stremio_account.has_unsupported_stream_shape(
                {
                    "name": "[RD+] Direct HTTPS",
                    "url": "https://media.example/video.mp4",
                }
            )
        )

    def test_resource_url_preserves_config_path_and_encodes_identity(self):
        self.assertEqual(
            stremio_account.resource_url(
                "https://addon.example/private-config/manifest.json",
                "stream",
                "series",
                "tt123:1:2",
            ),
            "https://addon.example/private-config/stream/series/tt123%3A1%3A2.json",
        )

    def test_account_subtitle_source_and_fetch_are_normalized(self):
        self.backend._post_json = mock.Mock(
            return_value={"result": {"addons": [descriptor()]}}
        )
        sources = self.backend.subtitle_sources("series")
        self.assertEqual(len(sources), 1)
        self.backend._fetch_json = mock.Mock(
            return_value={
                "subtitles": [
                    {
                        "lang": "eng",
                        "url": "https://subtitles.example/episode.vtt",
                    }
                ]
            }
        )
        subtitles = self.backend.fetch_subtitles(
            sources[0], "series", "tt123:1:2"
        )
        self.assertEqual(subtitles[0]["lang"], "eng")
        self.assertEqual(
            self.backend._fetch_json.call_args.args[0],
            "https://addon.example/config/subtitles/series/tt123%3A1%3A2.json",
        )

        self.backend.fetch_subtitles(
            sources[0],
            "series",
            "tt123:1:2",
            {
                "videoHash": "abc123",
                "videoSize": 123456,
                "filename": "Episode 1.mkv",
            },
        )
        self.assertEqual(
            self.backend._fetch_json.call_args.args[0],
            "https://addon.example/config/subtitles/series/tt123%3A1%3A2/"
            "videoHash=abc123&videoSize=123456&filename=Episode+1.mkv.json",
        )

    def test_tv_catalog_sources_require_matching_stream_capability(self):
        tv_addon = descriptor(name="Greek TV")
        tv_addon["manifest"].update(
            {
                "types": ["tv"],
                "resources": ["catalog", "stream"],
                "catalogs": [{"type": "tv", "id": "GreekTV", "name": "Greek TV"}],
            }
        )
        catalog_only = descriptor(name="Catalog only")
        catalog_only["manifest"].update(
            {
                "types": ["tv"],
                "resources": ["catalog"],
                "catalogs": [{"type": "tv", "id": "NoStreams"}],
            }
        )
        self.backend._post_json = mock.Mock(
            return_value={"result": {"addons": [tv_addon, catalog_only]}}
        )
        sources = self.backend.catalog_sources("tv")
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["id"], "GreekTV")
        self.backend._fetch_json = mock.Mock(
            return_value={"metas": [{"id": "grtv_ERTNews_gr", "name": "ERT News"}]}
        )
        metas = self.backend.fetch_catalog(
            sources[0]["source"], "tv", sources[0]["id"]
        )
        self.assertEqual(metas[0]["name"], "ERT News")
        self.assertEqual(
            self.backend._fetch_json.call_args.args[0],
            "https://addon.example/config/catalog/tv/GreekTV.json",
        )

    def test_link_config_writer_does_not_require_account_password(self):
        target = Path(self.temp_dir.name) / "linked" / "stremio_account.json"
        link_stremio_account.write_config(target, "linked-auth-key")
        self.assertEqual(
            json.loads(target.read_text(encoding="utf-8")),
            {"auth_key": "linked-auth-key"},
        )
        if os.name != "nt":
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)

    @mock.patch.object(
        link_stremio_account,
        "create_link",
        return_value=("private-code", "https://link.stremio.com/ABCD"),
    )
    @mock.patch.object(link_stremio_account, "read_auth_key")
    def test_link_manager_exposes_only_link_and_writes_key_after_approval(
        self, read_auth_key, _create_link
    ):
        target = Path(self.temp_dir.name) / "link" / "account.json"
        manager = link_stremio_account.AccountLinkManager(target)
        waiting = manager.start()
        self.assertEqual(waiting["state"], "waiting")
        self.assertEqual(waiting["link"], "https://link.stremio.com/ABCD")
        self.assertNotIn("private-code", json.dumps(waiting))

        read_auth_key.return_value = ""
        self.assertEqual(manager.status(poll=True)["state"], "waiting")
        read_auth_key.return_value = "private-auth-key"
        self.assertEqual(manager.status(poll=True), {"state": "connected"})
        self.assertEqual(
            json.loads(target.read_text(encoding="utf-8")),
            {"auth_key": "private-auth-key"},
        )
        with self.assertRaisesRegex(RuntimeError, "already connected"):
            manager.start()


if __name__ == "__main__":
    unittest.main()
