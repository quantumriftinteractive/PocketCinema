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
    def run_flow(self, items=(), failures=(), failed_ids='', languages='',
                 source_choice='All sources', audio_choice=''):
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
    'Stream source') printf '%s\n' "$TEST_SOURCE" ;;
    'Audio language (verified tags)')
      printf 'LANGUAGE OPTIONS\n' >>"$TEST_ROOT/trace"
      cut -f1 "$2" >>"$TEST_ROOT/trace"
      if [ -n "$TEST_AUDIO" ]; then
        cut -f1 "$2" | grep -Fx "$TEST_AUDIO" >/dev/null || {
          echo 'test requested an unavailable language' >&2
          return 1
        }
      fi
      printf '%s\n' "$TEST_AUDIO"
      ;;
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
                                         'TEST_SOURCE': source_choice, 'TEST_AUDIO': audio_choice,
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


    @staticmethod
    def stream(stream_id, source, languages, mode='direct', playable=True):
        return {'id': stream_id, 'playable': playable, 'name': source,
                'source_label': source, 'description': '', 'playback_mode': mode,
                'compatibility': {'audio_languages': languages}}

    def test_open_media_undefined_language_does_not_offer_other_sources_english(self):
        trace = self.run_flow(items=[self.stream('open', 'PocketCinema Open Media', ['und']),
                                     self.stream('other', 'Other source', ['eng'])],
                              source_choice='PocketCinema Open Media')
        self.assertNotIn('MENU Audio language', trace)
        self.assertIn('Keeping all audio languages.', trace)
        self.assertIn('PLAY open', trace)
        self.assertNotIn('No playable streams', trace)

    def test_language_menu_follows_selected_source_and_conversion_still_selected(self):
        trace = self.run_flow(items=[self.stream('english', 'English source', ['eng']),
                                     self.stream('spanish', 'Spanish source', ['spa'], 'convert')],
                              source_choice='Spanish source', audio_choice='spa (verified)')
        self.assertIn('All audio languages', trace)
        self.assertIn('spa (verified)', trace)
        self.assertNotIn('eng (verified)', trace)
        self.assertIn('PLAY spanish', trace)

    def test_all_sources_retains_union_of_available_languages(self):
        trace = self.run_flow(items=[self.stream('english', 'English source', ['eng']),
                                     self.stream('spanish', 'Spanish source', ['spa'])],
                              audio_choice='spa (verified)')
        self.assertIn('eng (verified)', trace)
        self.assertIn('spa (verified)', trace)
        self.assertIn('PLAY spanish', trace)

    def test_all_audio_keeps_undefined_stream_in_selected_source(self):
        trace = self.run_flow(items=[self.stream('undefined', 'Mixed source', ['und']),
                                     self.stream('english', 'Mixed source', ['eng'])],
                              source_choice='Mixed source', audio_choice='All audio languages')
        self.assertIn('All audio languages', trace)
        self.assertIn('eng (verified)', trace)
        self.assertNotIn('und (verified)', trace)
        self.assertIn('PLAY undefined', trace)

    def test_selected_language_filters_streams_within_selected_source(self):
        trace = self.run_flow(items=[self.stream('undefined', 'Mixed source', ['und']),
                                     self.stream('english', 'Mixed source', ['eng'])],
                              source_choice='Mixed source', audio_choice='eng (verified)')
        self.assertIn('PLAY english', trace)
        self.assertNotIn('PLAY undefined', trace)

    def test_failed_and_unplayable_streams_cannot_supply_language_choices(self):
        trace = self.run_flow(items=[self.stream('good', 'Source', ['eng']),
                                     self.stream('failed', 'Source', ['rus']),
                                     self.stream('blocked', 'Source', ['tur'], playable=False)],
                              failed_ids='|failed|', source_choice='Source')
        self.assertIn('eng (verified)', trace)
        self.assertNotIn('rus (verified)', trace)
        self.assertNotIn('tur (verified)', trace)
        self.assertIn('PLAY good', trace)

    def test_missing_empty_and_undefined_tags_remain_selectable(self):
        for tags in (None, [], ['', 'UND']):
            with self.subTest(tags=tags):
                stream = self.stream('unknown', 'Source', tags)
                if tags is None:
                    del stream['compatibility']['audio_languages']
                trace = self.run_flow(items=[stream], source_choice='Source')
                self.assertNotIn('MENU Audio language', trace)
                self.assertIn('PLAY unknown', trace)

    def test_saved_audio_preference_still_selects_matching_stream(self):
        trace = self.run_flow(items=[self.stream('undefined', 'Source', ['und']),
                                     self.stream('english', 'Source', ['eng'])],
                              source_choice='Source', languages='eng')
        self.assertNotIn('MENU Audio language', trace)
        self.assertIn('PLAY english', trace)


if __name__ == '__main__':
    unittest.main()
