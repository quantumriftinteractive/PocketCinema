"""Characterize the existing player-log readiness gate; no SDL or media runs."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest


UI = Path(__file__).resolve().parents[1] / 'client/miyoo/pocketcinema-ui.sh'


@unittest.skipUnless(shutil.which('sh'), 'requires POSIX shell')
class PlaybackReadinessTests(unittest.TestCase):
    def run_player(self, marker):
        body = re.search(r'^play_url\(\) \{\n.*?^\}', UI.read_text(), re.M | re.S)[0]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            body = body.replace('/tmp/', directory + '/')
            script = body + r'''
log() { printf '%s\n' "$*" >>"$TRACE"; }
stop_loading() {
  if kill -0 "$ffplay_pid" 2>/dev/null; then
    log OVERLAY_STOP_PLAYER_RUNNING
    touch "$SYS_DIR/overlay-dismissed"
  else
    log OVERLAY_STOP_PLAYER_EXITED
  fi
}
sleep() { command sleep 0.02; }
run_ffplay() {
  log PLAYER_START
  printf 'Input #0, simulated media\n'
  [ "$TEST_MARKER" != 1 ] || printf 'SDL_SetVideoMode simulated surface\n'
  if [ "$TEST_MARKER" = 1 ]; then
    # Keep the simulated player alive until dismissal, with a bounded deadline.
    attempt=0
    while [ ! -f "$SYS_DIR/overlay-dismissed" ] && [ "$attempt" -lt 150 ]; do
      command sleep 0.02
      attempt=$((attempt + 1))
    done
  else
    command sleep 0.15
  fi
}
classify_playback_error() { printf 'Simulated missing readiness'; }
playback_server_error() { :; }
RESOURCE_MONITOR=/nonexistent-resource-monitor
PAUSE_MONITOR=/nonexistent-pause-monitor
PLAYBACK_CONTROL=/nonexistent-control
PLAYBACK_CONTROL_FILE="$SYS_DIR/control"
LOG_FILE="$SYS_DIR/player-output"
FIELD_TEST=0
play_url 'opaque-test-session' 0 '' 0
log "RESULT rc=$? valid=$PLAYBACK_VALID"
'''
            result = subprocess.run(['sh'], input=script, capture_output=True, text=True, timeout=10,
                                    env={**os.environ, 'TRACE': str(root / 'trace'),
                                         'SYS_DIR': directory, 'TEST_MARKER': str(int(marker))})
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stderr, '')
            return (root / 'trace').read_text()

    def test_expected_log_marker_dismisses_overlay_while_player_runs(self):
        trace = self.run_player(True)
        self.assertIn('OVERLAY_STOP_PLAYER_RUNNING', trace)
        self.assertIn('ffplay video ready', trace)
        self.assertIn('RESULT rc=0 valid=1', trace)

    def test_missing_log_marker_leaves_overlay_until_player_ends(self):
        trace = self.run_player(False)
        self.assertNotIn('OVERLAY_STOP_PLAYER_RUNNING', trace)
        self.assertIn('OVERLAY_STOP_PLAYER_EXITED', trace)
        self.assertNotIn('ffplay video ready', trace)
        self.assertIn('RESULT rc=1 valid=0', trace)


if __name__ == '__main__':
    unittest.main()
