"""Execute the production BusyBox-compatible flow with network/SDL stubs."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest


UI = Path(__file__).resolve().parents[1] / 'client/miyoo/pocketcinema-ui.sh'


@unittest.skipUnless(shutil.which('jq') and shutil.which('sh'), 'requires sh and jq')
class StreamSelectionTests(unittest.TestCase):
    def run_flow(self, items=(), failures=(), failed_ids='', languages=''):
        source = UI.read_text()
        functions = '\n'.join(
            re.search(r'^' + name + r'\(\) \{\n.*?^\}', source, re.M | re.S)[0]
            for name in ('show_no_playable_streams', 'streams_flow')
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'response.json').write_text(json.dumps({'items': list(items), 'failures': list(failures)}))
            # Isolate all production /tmp paths, including selector intermediate files.
            functions = functions.replace('/tmp/pocketcinema-', directory + '/pocketcinema-')
            script = functions + r'''
log() { :; }
start_loading() { :; }
stop_loading() { :; }
api_get() { cat "$TEST_ROOT/response.json"; }
message() { printf 'MESSAGE %s: %s\n' "$1" "$2" >>"$TEST_ROOT/trace"; }
language_order_names() { printf '%s' "$1"; }
select_from_file() {
  printf 'MENU %s\n' "$1" >>"$TEST_ROOT/trace"
  case "$1" in
    'Stream source') printf 'All sources\n' ;;
    'Stream Details') printf 'Use this stream\n' ;;
    'Select Stream') head -n 1 "$2" | cut -f1 ;;
    *) printf '\n' ;;
  esac
}
select_audio_track() { printf '0'; }
play_selected_stream() { printf 'PLAY %s\n' "$6" >>"$TEST_ROOT/trace"; }
FIELD_TEST=1
AUTO_FIRST=0
streams_flow movie example 'Test title' 2026
'''
            result = subprocess.run(['sh'], input=script, text=True, capture_output=True,
                                    env={**os.environ, 'TEST_ROOT': directory, 'JQ': shutil.which('jq'),
                                         'FAILED_STREAM_IDS': failed_ids, 'AUDIO_LANGUAGES': languages,
                                         'AUDIO_FALLBACK': 'ask', 'POCKETCINEMA_DRY_RUN': '0'})
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stderr, '')
            return (root / 'trace').read_text()

    def test_empty_list_skips_all_selection_menus(self):
        trace = self.run_flow()
        self.assertIn('No playable streams available', trace)
        self.assertNotIn('MENU', trace)
        self.assertNotIn('No verified tags', trace)

    def test_multiple_source_failures_are_preserved(self):
        trace = self.run_flow(failures=[{'source': 'Addon A', 'message': 'Unavailable'},
                                        {'source': 'Addon B', 'message': 'Inspection timed out'}])
        self.assertIn('Addon A: Unavailable', trace)
        self.assertIn('Addon B: Inspection timed out', trace)
        self.assertNotIn('MENU', trace)

    def test_optional_local_files_is_context_after_other_failures(self):
        trace = self.run_flow(failures=[{'source': 'Stremio Service Local Files',
                                         'message': 'Stremio Service Local Files is disabled'},
                                        {'source': 'Account addon', 'message': 'Unavailable'}])
        self.assertIn('No playable streams available', trace)
        self.assertLess(trace.index('Account addon: Unavailable'), trace.index('Local Files: disabled (optional)'))
        self.assertNotIn('MENU', trace)

    def test_failed_or_unplayable_items_skip_menus_even_with_saved_language(self):
        trace = self.run_flow(items=[{'id': 'failed', 'playable': True}, {'id': 'blocked', 'playable': False}],
                              failed_ids='|failed|', languages='eng')
        self.assertIn('No playable streams available', trace)
        self.assertNotIn('MENU', trace)

    def test_failure_notices_are_bounded_and_urls_removed(self):
        trace = self.run_flow(failures=[{'source': 'Addon', 'message': 'Failed https://example.com/private-token\n' + 'x' * 200}] * 5)
        self.assertNotIn('private-token', trace)
        self.assertIn('[URL]', trace)
        self.assertIn('More source notices: 2', trace)
        for line in trace.splitlines()[1:4]:
            self.assertLessEqual(len(line), 64)

    def test_successful_selection_reaches_existing_playback_path(self):
        trace = self.run_flow(items=[{'id': 'good', 'playable': True, 'name': 'Public source',
                                     'source_label': 'Public source', 'description': '',
                                     'playback_mode': 'direct', 'compatibility': {'audio_languages': ['eng']}}])
        self.assertIn('MENU Stream source', trace)
        self.assertIn('MENU Select Stream', trace)
        self.assertIn('MENU Stream Details', trace)
        self.assertIn('PLAY good', trace)
        self.assertNotIn('No playable streams', trace)


if __name__ == '__main__':
    unittest.main()
