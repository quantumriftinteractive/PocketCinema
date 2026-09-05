"""Focused regression checks for Windows background helper creation flags."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from server import playback_compatibility, pocketcinema_server, transcoding


class WindowsProcessSilenceTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "Windows process creation flags")
    def test_stream_probe_captures_output_without_a_console(self):
        result = mock.Mock(returncode=0, stdout="{}")
        with mock.patch.object(playback_compatibility.subprocess, "run", return_value=result) as run:
            self.assertEqual(playback_compatibility.probe_media("ffprobe.exe", "http://127.0.0.1/video"), {})
        self.assertEqual(run.call_args.kwargs["creationflags"], playback_compatibility.subprocess.CREATE_NO_WINDOW)
        self.assertTrue(run.call_args.kwargs["capture_output"])

    @unittest.skipUnless(os.name == "nt", "Windows process creation flags")
    def test_subtitle_conversion_keeps_stderr_capture_without_a_console(self):
        with tempfile.TemporaryDirectory() as directory:
            def convert(command, cwd, **kwargs):
                Path(cwd, command[-1]).write_text("1\n00:00:00,000 --> 00:00:01,000\ntext\n", encoding="utf-8")
                return mock.Mock(returncode=0)

            with mock.patch.object(transcoding.subprocess, "run", side_effect=convert) as run:
                output = transcoding.normalize_subtitle_payload("ffmpeg.exe", b"[Script Info]\n", directory)
                self.assertTrue(output.is_file())
            self.assertEqual(run.call_args.kwargs["creationflags"], transcoding.subprocess.CREATE_NO_WINDOW)
            self.assertEqual(run.call_args.kwargs["stderr"], transcoding.subprocess.PIPE)

    @unittest.skipUnless(os.name == "nt", "Windows process creation flags")
    def test_transcode_resource_probe_is_hidden_but_captured(self):
        result = mock.Mock(returncode=0, stdout="10 2.5")
        with mock.patch.object(pocketcinema_server.subprocess, "run", return_value=result) as run:
            sample = pocketcinema_server.TranscodeResourceMonitor.sample(123)
        self.assertEqual(sample, (0, 2.5, "cpu_seconds"))
        self.assertEqual(run.call_args.kwargs["creationflags"], pocketcinema_server.subprocess.CREATE_NO_WINDOW)
        self.assertTrue(run.call_args.kwargs["capture_output"])


if __name__ == "__main__":
    unittest.main()
