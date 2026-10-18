"""Execute client lifecycle functions with real children and isolated proc fixtures.

macOS has no Linux procfs: lifecycle tests substitute a host-only ps adapter.
The production proc parser is tested separately against Linux-format fixtures.
"""
import os
from pathlib import Path
import re
import shutil
import shlex
import signal
import subprocess
import sys
import tempfile
import time
import unittest

UI = Path(__file__).resolve().parents[1] / 'client/miyoo/pocketcinema-ui.sh'
HELPERS = ('process_snapshot', 'record_launch_owner', 'capture_process_identity',
           'owned_process_state', 'signal_owned_process', 'wait_owned_exit',
           'stop_owned_process', 'fail_display_handoff', 'abort_display_handoff',
           'require_display_safe', 'start_loading', 'stop_loading',
           'preserve_ffplay_diagnostics')


def functions(*names):
    source = UI.read_text()
    return '\n'.join(re.search(r'^' + name + r'\(\) [\{\(]\n.*?^[\}\)]', source,
                               re.M | re.S)[0] for name in names)


# Host-only identity oracle. Never shipped; actual signal targets remain real
# children. Linux production parsing is covered by the fixture tests below.
PROBE = '''import os, pathlib, subprocess, sys, zlib
root = pathlib.Path(os.environ['SYS_DIR'])
pid = sys.argv[1]
r = subprocess.run(['ps', '-p', pid, '-o', 'ppid=', '-o', 'lstart=', '-o', 'stat='],
                   capture_output=True, text=True)
f = r.stdout.split()
if not f:
    sys.exit(1)
parent, state = f[0], f[-1][0]
ticks = str(zlib.crc32(' '.join(f[1:-1]).encode()))
if (root / 'tamper').exists() and (root / 'panel-pid').exists() and pid == (root / 'panel-pid').read_text():
    if os.environ['TEST_PANEL'] == 'missing':
        sys.exit(2)
    ticks = str(int(ticks) + 1)
print(parent + ':' + ticks + ':' + state)
'''

PANEL = '''import os, pathlib, signal, time
root = pathlib.Path(os.environ['SYS_DIR'])
mode = os.environ['TEST_PANEL']
quit_requested = False
def term(sig, frame):
    global quit_requested
    quit_requested = True
    with (root / 'trace').open('a') as f:
        f.write('PANEL_TERM_FLAG\\n')
signal.signal(signal.SIGTERM, term)
(root / 'panel-pid').write_text(str(os.getpid()))
while True:
    if mode in ('already', 'nonzero', 'crash') and (root / 'panel-release').exists():
        if mode == 'crash':
            os.kill(os.getpid(), signal.SIGKILL)  # crash-like signal exit, no core
        raise SystemExit(9 if mode == 'nonzero' else 0)
    if mode not in ('term', 'survive') and (root / 'dismiss_info_panel').exists():
        time.sleep(0.02)
        with (root / 'trace').open('a') as f:
            f.write('PANEL_CLEANUP\\n')
        break
    # Onion's TERM handler only changes quit; persistent loop ignores it.
    time.sleep(0.005)
'''

PLAYER = '''import os, pathlib, signal, time
root = pathlib.Path(os.environ['SYS_DIR'])
mode = os.environ['TEST_MODE']
(root / 'player-pid').write_text(str(os.getpid()))
with (root / 'trace').open('a') as f:
    try:
        os.kill(int((root / 'panel-pid').read_text()), 0)
        f.write('PLAYER_OVERLAPS_PANEL\\n')
    except ProcessLookupError:
        pass
    f.write('PLAYER_START\\n')
print('Input #0, simulated media', flush=True)
print('player stderr captured', file=__import__('sys').stderr, flush=True)
if mode == 'early':
    print('video initialization failed', file=__import__('sys').stderr, flush=True)
    raise SystemExit(7)
if mode != 'quiet':
    print('SDL_SetVideoMode simulated surface', flush=True)
def term(sig, frame):
    print('player cancellation diagnostic', file=__import__('sys').stderr, flush=True)
    raise SystemExit(0)
signal.signal(signal.SIGTERM, term)
(root / 'player-running').touch()
if mode == 'cancel':
    while True:
        time.sleep(0.01)
time.sleep(0.6)
'''

CONTROL = '''import os, pathlib, signal, time, sys
root = pathlib.Path(os.environ['SYS_DIR'])
(root / 'control-pid').write_text(str(os.getpid()))
def term(sig, frame):
    with (root / 'trace').open('a') as f:
        f.write('CONTROL_STOPPED\\n')
    raise SystemExit(0)
signal.signal(signal.SIGTERM, term)
while True:
    time.sleep(0.01)
'''


PAUSE = '''import os, pathlib, signal, sys, time
root = pathlib.Path(os.environ['SYS_DIR'])
with (root / 'trace').open('a') as f:
    f.write('PAUSE_START\\n')
def term(sig, frame):
    pathlib.Path(sys.argv[1]).write_text('0')
    raise SystemExit(0)
signal.signal(signal.SIGTERM, term)
while True:
    time.sleep(0.01)
'''


@unittest.skipUnless(shutil.which('sh') and shutil.which('ps'), 'requires POSIX shell and host ps')
class PlaybackReadinessTests(unittest.TestCase):
    def run_player(self, mode='ready', panel='normal', cancel=False, tracking=False):
        body = functions(*HELPERS, 'run_ffplay', 'play_url', 'cleanup')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            body = body.replace('/tmp/', directory + '/')
            for name, code in [('probe', PROBE), ('panel', PANEL), ('player', PLAYER), ('control', CONTROL), ('pause', PAUSE)]:
                (root / (name + '.py')).write_text(code)
                launcher = root / name
                launcher.write_text('#!/bin/sh\nexec ' + shlex.quote(sys.executable) + ' '
                                    + shlex.quote(str(root / (name + '.py'))) + ' "$@"\n')
                launcher.chmod(0o700)
            script = body + r'''
log() { printf '%s\n' "$*" >>"$TRACE"; }
sleep() { command sleep 0.05; }
record_launch_owner() { LAUNCH_OWNER=$$; }
process_snapshot() { "$SYS_DIR/probe" "$1"; }
stop_server_monitor() { :; }
classify_playback_error() { printf 'Simulated video startup failure'; }
playback_server_error() { :; }
kill() {
  log "SIGNAL $*"
  if [ "$TEST_PANEL" = survive ]; then return 1; fi
  command kill "$@"
}
RESOURCE_MONITOR=/nonexistent-resource-monitor
PAUSE_MONITOR=/nonexistent-pause-monitor
[ "$TEST_TRACKING" != 1 ] || PAUSE_MONITOR="$SYS_DIR/pause"
PLAYBACK_CONTROL=/nonexistent-control
[ "$TEST_MODE" != cancel ] || PLAYBACK_CONTROL="$SYS_DIR/control"
PLAYBACK_CONTROL_FILE="$SYS_DIR/control-request"
LOG_FILE="$SYS_DIR/player-output"
DISPLAY_FAILURE_FILE="$SYS_DIR/display-failure"
FIELD_TEST=0
CANDIDATE_PLAYER=0
FFPLAY="$SYS_DIR/player"
PADSP=""
FFPLAY_PID=""
FFPLAY_ID=""
trap 'cleanup; log CLEANUP_DONE' EXIT
trap 'exit 143' TERM
start_loading PocketCinema 'Preparing video and selectable subtitles...'
while [ ! -f "$SYS_DIR/panel-pid" ]; do command sleep 0.005; done
FIELD_TEST_SUBTITLE_FILE="$SYS_DIR/subtitle.mkv"
printf 'subtitle fixture' >"$FIELD_TEST_SUBTITLE_FILE"
case "$TEST_PANEL" in
  already|nonzero|crash)
    touch "$SYS_DIR/panel-release"
    while owned_process_state "$LOADING_PID" "$LOADING_ID"; do command sleep 0.01; done ;;
  changed|missing) touch "$SYS_DIR/tamper" ;;
esac
log PREPARATION_COMPLETE
play_url 'opaque-test-session' 0 "$SYS_DIR/subtitle.mkv" 1
log "RESULT rc=$? valid=$PLAYBACK_VALID watched=$PLAYBACK_ELAPSED pause=$PAUSE_TRACKING_VALID"
'''
            env = {**os.environ, 'TRACE': str(root / 'trace'), 'SYS_DIR': directory,
                   'TEST_MODE': mode, 'TEST_PANEL': panel, 'INFOPANEL': str(root / 'panel'),
                   'TEST_TRACKING': str(int(tracking))}
            process = subprocess.Popen(['sh'], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, text=True, env=env)
            try:
                process.stdin.write(script)
                process.stdin.close()
                process.stdin = None
                if cancel:
                    self.wait_file(root / ('control-pid' if mode == 'cancel' else 'dismiss_info_panel'), process)
                    process.terminate()
                stdout, stderr = process.communicate(timeout=20)
                bad_panel = panel not in ('normal', 'already')
                self.assertEqual(process.returncode, 143 if cancel else (1 if bad_panel else 0), stderr)
                self.assertEqual(stdout, '')
                trace = (root / 'trace').read_text()
                output = (root / 'player-output').read_text() if (root / 'player-output').exists() else ''
                self.assertFalse((root / 'dismiss_info_panel').exists())
                self.assertFalse((root / 'stay_awake').exists())
                self.assertFalse((root / 'subtitle.mkv').exists())
                self.assertFalse((root / 'pocketcinema-ffplay.log').exists())
                self.assertIn('CLEANUP_DONE', trace)
                self.assertNotIn('PLAYER_OVERLAPS_PANEL', trace)
                if bad_panel:
                    self.assertNotIn('PLAYER_START', trace)
                    self.assertIn('display handoff unsafe', trace)
                if panel in ('changed', 'missing'):
                    self.assertNotIn('SIGNAL', trace)
                if mode == 'cancel' and (root / 'player-pid').exists():
                    with self.assertRaises(ProcessLookupError):
                        os.kill(int((root / 'player-pid').read_text()), 0)
                return trace, output
            finally:
                if process.poll() is None:
                    process.kill()
                    process.communicate()
                # Test-only cleanup for deliberately unverifiable/surviving fixtures.
                for name in ('panel-pid', 'control-pid', 'player-pid'):
                    if (root / name).exists():
                        pid = int((root / name).read_text())
                        command = subprocess.run(['ps', '-p', str(pid), '-o', 'command='],
                                                 capture_output=True, text=True).stdout
                        fixture = {'panel-pid': 'panel.py', 'control-pid': 'control.py',
                                   'player-pid': 'player.py'}[name]
                        if str(root / fixture) in command:
                            try:
                                os.kill(pid, signal.SIGKILL)
                            except ProcessLookupError:
                                pass

    def wait_file(self, path, process):
        deadline = time.monotonic() + 10
        while not path.exists():
            if process.poll() is not None or time.monotonic() > deadline:
                self.fail('fixture did not reach ' + path.name)
            time.sleep(0.005)

    def test_graceful_onion_like_panel_cleanup_precedes_player(self):
        trace, output = self.run_player()
        self.assertLess(trace.index('PANEL_CLEANUP'), trace.index('PLAYER_START'))
        self.assertLess(trace.index('PLAYER_START'), trace.index('ffplay video ready'))
        self.assertIn('state=clean rc=0', trace)
        self.assertIn('RESULT rc=0 valid=1', trace)
        self.assertIn('player stderr captured', output)

    def test_already_exited_successfully_is_reaped(self):
        trace, _ = self.run_player(panel='already')
        self.assertIn('loading exit', trace)
        self.assertIn('state=clean rc=0', trace)
        self.assertIn('PLAYER_START', trace)

    def test_missing_marker_does_not_invent_watched_time(self):
        trace, output = self.run_player(mode='quiet')
        self.assertNotIn('ffplay video ready', trace)
        self.assertIn('RESULT rc=1 valid=0 watched=0 pause=0', trace)
        self.assertIn('player stderr captured', output)

    def test_early_failure_preserves_diagnostics(self):
        trace, output = self.run_player(mode='early')
        self.assertIn('RESULT rc=7 valid=0 watched=0 pause=0', trace)
        self.assertIn('video initialization failed', output)

    def test_pause_tracking_begins_only_after_existing_readiness_marker(self):
        trace, _ = self.run_player(tracking=True)
        self.assertLess(trace.index('ffplay video ready'), trace.index('PAUSE_START'))
        self.assertRegex(trace, r'RESULT rc=0 valid=1 watched=\d+ pause=1')
        trace, _ = self.run_player(mode='quiet', tracking=True)
        self.assertNotIn('PAUSE_START', trace)
        self.assertIn('watched=0 pause=0', trace)

    def test_nonzero_panel_blocks_player(self):
        trace, _ = self.run_player(panel='nonzero')
        self.assertIn('state=abnormal rc=9', trace)

    def test_crashed_panel_blocks_player(self):
        trace, _ = self.run_player(panel='crash')
        self.assertIn('state=abnormal', trace)

    def test_changed_identity_never_signaled(self):
        self.run_player(panel='changed')

    def test_unreadable_identity_never_signaled(self):
        self.run_player(panel='missing')

    def test_term_handler_only_sets_quit_then_kill_is_bounded(self):
        trace, _ = self.run_player(panel='term')
        self.assertIn('PANEL_TERM_FLAG', trace)
        self.assertIn('requesting KILL', trace)
        self.assertIn('state=forced', trace)

    def test_surviving_panel_blocks_display_without_waiting_forever(self):
        trace, _ = self.run_player(panel='survive')
        self.assertIn('state=alive', trace)

    def test_cancellation_during_handoff(self):
        trace, _ = self.run_player(panel='term', cancel=True)
        self.assertNotIn('PLAYER_START', trace)

    def test_cancellation_after_player_launch_stops_control_and_saves_output(self):
        trace, output = self.run_player(mode='cancel', cancel=True)
        self.assertIn('CONTROL_STOPPED', trace)
        self.assertIn('player cancellation diagnostic', output)
        self.assertIn('player stderr captured', output)
        self.assertNotIn('RESULT', trace)


class ProcessIdentityTests(unittest.TestCase):
    def run_shell(self, script, root):
        return subprocess.run(['sh'], input=script, text=True, capture_output=True,
                              timeout=5, env={**os.environ, 'TEST_ROOT': str(root)})

    def test_linux_stat_parser_with_spaces_and_parentheses(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'self').mkdir()
            (root / 'self/stat').write_text('available\n')
            (root / '123').mkdir()
            fields = ['S', '99'] + ['0'] * 17 + ['789'] + ['0'] * 8
            (root / '123/stat').write_text('123 (info panel ) name) ' + ' '.join(fields) + '\n')
            script = functions('process_snapshot').replace('/proc/', directory + '/')
            r = self.run_shell(script + '\nprocess_snapshot 123\n', root)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(r.stdout, '99:789:S\n')

    def test_unavailable_or_malformed_proc_refuses_identity(self):
        for malformed in (False, True):
            with self.subTest(malformed=malformed), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                if malformed:
                    (root / 'self').mkdir()
                    (root / 'self/stat').write_text('available\n')
                    (root / '123').mkdir()
                    (root / '123/stat').write_text('not Linux stat\n')
                script = functions('process_snapshot').replace('/proc/', directory + '/')
                r = self.run_shell(script + '\nprocess_snapshot 123\n', root)
                self.assertEqual(r.returncode, 2)

    def test_stale_or_changed_identity_between_wait_and_signal_is_refused(self):
        for snapshot in ('different:456:S', '99:457:S', ''):
            with self.subTest(snapshot=snapshot), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                script = functions('owned_process_state', 'signal_owned_process')
                script += '\nprocess_snapshot() { printf "%s\\n" ' + shlex.quote(snapshot) + '; }\n'
                script += 'kill() { echo UNSAFE_SIGNAL; }\nsignal_owned_process 123 99:456 TERM\n'
                r = self.run_shell(script, root)
                self.assertEqual(r.returncode, 2)
                self.assertNotIn('UNSAFE_SIGNAL', r.stdout)

    def test_failed_handoff_latch_survives_command_substitution(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = functions('fail_display_handoff', 'abort_display_handoff', 'require_display_safe')
            script += r'''
log() { :; }
DISPLAY_FAILURE_FILE="$TEST_ROOT/failure"
value=$(fail_display_handoff)
require_display_safe
echo UNSAFE_DISPLAY
'''
            r = self.run_shell(script, root)
            self.assertEqual(r.returncode, 1)
            self.assertNotIn('UNSAFE_DISPLAY', r.stdout)


@unittest.skipUnless(shutil.which('jq'), 'requires jq')
class CallerFailureTests(unittest.TestCase):
    def test_callers_abort_before_any_subsequent_display_or_player(self):
        cases = [
            ('start_loading', 'start_loading Title Message'),
            ('play_url', "play_url opaque 0 '' 0"),
            ('message', 'message Title Message timed'),
            ('discover_local_pcserver', 'discover_local_pcserver'),
            ('validate_setup_pcserver_url', 'validate_setup_pcserver_url Local http://example.invalid ""'),
            ('live_tv_flow', 'live_tv_flow'),
            ('library_items_flow', 'library_items_flow movie Movies'),
            ('account_flow', 'account_flow'),
            ('streams_flow', 'streams_flow movie example Title 2026'),
            ('fallback_matroska_playback', 'fallback_matroska_playback reason movie example Title 2026 0 stream'),
            ('play_selected_stream', 'play_selected_stream movie example Title 2026 0 stream none'),
            ('select_matroska_subtitle_fallback', 'select_matroska_subtitle_fallback movie example stream'),
            ('select_subtitle', 'select_subtitle movie example stream'),
        ]
        for name, invocation in cases:
            with self.subTest(caller=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                script = functions('fail_display_handoff', 'abort_display_handoff', 'require_display_safe', name)
                script = script.replace('/tmp/', directory + '/')
                script += r'''
log() { :; }
stop_loading() { fail_display_handoff; return 1; }
api_get() { printf '{"count":0,"items":[]}'; return 1; }
api_post_play() { return 1; }
validate_pcserver_url_with_proxy() { return 1; }
select_from_file() { echo UNSAFE_SELECTOR; }
run_ffplay() { echo UNSAFE_PLAYER; }
message() { echo UNSAFE_MESSAGE; }
'''
                # Preserve the real function under test when a stub shares its name.
                if name == 'message':
                    script += functions('message').replace('/tmp/', directory + '/') + '\n'
                if name != 'start_loading':
                    script += 'start_loading() { :; }\n'
                if name == 'select_matroska_subtitle_fallback':
                    script += 'language_order_names() { :; }\nSUBTITLE_LANGUAGES=spa\n'
                if name == 'select_subtitle':
                    script += 'SUBTITLES=1\nSUBTITLE_FALLBACK=ask\n'
                script += '\nDISPLAY_FAILURE_FILE="$TEST_ROOT/failure"\n'
                script += 'DISCOVERY_CLIENT=/usr/bin/true\nFIELD_TEST=0\nMATROSKA_SUBTITLES=0\n'
                script += 'JQ=' + shlex.quote(shutil.which('jq')) + '\n'
                script += invocation + '\necho UNSAFE_CONTINUED\n'
                r = subprocess.run(['sh'], input=script, text=True, capture_output=True, timeout=5,
                                   env={**os.environ, 'TEST_ROOT': directory})
                self.assertEqual(r.returncode, 1, r.stderr + r.stdout)
                self.assertNotIn('UNSAFE_', r.stdout)


    def test_playback_shutdown_failure_across_setup_and_direct_branches(self):
        for mode in ('transport', 'rejected', 'field-rejected', 'direct', 'no-tracks'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                script = functions('fail_display_handoff', 'abort_display_handoff',
                                   'play_selected_stream').replace('/tmp/', directory + '/')
                script += r'''
log() { :; }
start_loading() { :; }
stop_loading() { fail_display_handoff; return 1; }
api_get() { printf '{"count":0}'; }
api_post_play() {
  [ "$MODE" != transport ] || return 1
  if [ "$MODE" = rejected ]; then printf '{"url":""}'; else printf '{"url":"opaque","field_test":false}'; fi
}
save_last_play() { :; }
message() { echo UNSAFE_MESSAGE; }
play_url() { echo UNSAFE_PLAYER; }
FIELD_TEST=0
MATROSKA_SUBTITLES=0
CANDIDATE_PLAYER=1
FFPLAY=/usr/bin/true
[ "$MODE" != field-rejected ] || FIELD_TEST=1
[ "$MODE" != no-tracks ] || MATROSKA_SUBTITLES=1
DISPLAY_FAILURE_FILE="$TEST_ROOT/failure"
play_selected_stream movie example Title 2026 0 stream none
echo UNSAFE_CONTINUED
'''
                r = subprocess.run(['sh'], input=script, text=True, capture_output=True, timeout=5,
                                   env={**os.environ, 'TEST_ROOT': directory, 'MODE': mode,
                                        'JQ': shutil.which('jq')})
                self.assertEqual(r.returncode, 1, r.stderr + r.stdout)
                self.assertNotIn('UNSAFE_', r.stdout)

    def test_account_creation_and_poll_shutdown_failure(self):
        for fail_at in (2, 3):
            with self.subTest(fail_at=fail_at), tempfile.TemporaryDirectory() as directory:
                script = functions('fail_display_handoff', 'abort_display_handoff', 'account_flow')
                script = script.replace('/tmp/', directory + '/') + r'''
log() { :; }
start_loading() { :; }
stop_count=0
stop_loading() {
  stop_count=$((stop_count + 1))
  [ "$stop_count" = "$FAIL_AT" ] || return 0
  fail_display_handoff
  return 1
}
api_get() { printf '{"configured":false}'; }
api_post_empty() { printf '{"link":"opaque-test-approval"}'; }
select_from_file() { printf 'Connect Account'; }
show_account_qr() { printf refresh; }
message() { echo UNSAFE_MESSAGE; }
DISPLAY_FAILURE_FILE="$TEST_ROOT/failure"
account_flow
echo UNSAFE_CONTINUED
'''
                r = subprocess.run(['sh'], input=script, text=True, capture_output=True, timeout=5,
                                   env={**os.environ, 'TEST_ROOT': directory, 'FAIL_AT': str(fail_at),
                                        'JQ': shutil.which('jq')})
                self.assertEqual(r.returncode, 1, r.stderr + r.stdout)
                self.assertNotIn('UNSAFE_', r.stdout)

    def test_no_unhandled_stop_loading_callers_remain(self):
        # Supplement executable branch tests with a complete call-site audit.
        caller = ''
        for line in UI.read_text().splitlines():
            if re.match(r'^\w+\(\)', line):
                caller = line.split('(')[0]
            if line.strip().startswith('stop_loading ') and caller != 'cleanup':
                self.assertIn('|| abort_display_handoff', line)


if __name__ == '__main__':
    unittest.main()
