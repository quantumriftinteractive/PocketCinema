#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
UI_SCRIPT="$SCRIPT_DIR/../client/miyoo/pocketstremio-ui.sh"

assert_contains() {
  printf '%s\n' "$1" | grep -F -q -- "$2" || {
    printf 'expected [%s] in proxy status-refresh path\n' "$2" >&2
    exit 1
  }
}

line_number() {
  printf '%s\n' "$1" | grep -n -F -- "$2" | head -n 1 | cut -d: -f1
}

activate_http_proxy_body=$(awk '
  /^activate_http_proxy\(\)/ { active = 1 }
  active { print }
  active && /^}/ { exit }
' "$UI_SCRIPT")
start_server_monitor_body=$(awk '
  /^start_server_monitor\(\)/ { active = 1 }
  active { print }
  active && /^}/ { exit }
' "$UI_SCRIPT")
http_proxy_flow_body=$(awk '
  /^http_proxy_flow\(\)/ { active = 1 }
  active { print }
  active && /^}/ { exit }
' "$UI_SCRIPT")

# Every successful effective proxy update restarts the established monitor.
assert_contains "$activate_http_proxy_body" 'save_http_proxy "$new_proxy"'
assert_contains "$activate_http_proxy_body" 'PROXY="$new_proxy"'
assert_contains "$activate_http_proxy_body" 'start_server_monitor'
save_line=$(line_number "$activate_http_proxy_body" 'save_http_proxy "$new_proxy"')
proxy_line=$(line_number "$activate_http_proxy_body" 'PROXY="$new_proxy"')
refresh_line=$(line_number "$activate_http_proxy_body" 'start_server_monitor')
[ "$save_line" -lt "$proxy_line" ] && [ "$proxy_line" -lt "$refresh_line" ] || {
  printf 'proxy save, activation, and refresh order is incorrect\n' >&2
  exit 1
}

# The reused monitor invalidates any stale result before using curl_request's
# current transport for the normal PSS /api/status validation.
assert_contains "$start_server_monitor_body" 'write_server_status "Server: Connecting..."'
assert_contains "$start_server_monitor_body" 'curl_request -fsS --connect-timeout 3 --max-time 5'
assert_contains "$start_server_monitor_body" '"$SERVER_BASE/api/status"'

# Edit, restore-default, and disable all share activate_http_proxy.
assert_contains "$http_proxy_flow_body" 'activate_http_proxy "$normalized_proxy"'
assert_contains "$http_proxy_flow_body" 'activate_http_proxy "$POCKETSTREMIO_DEFAULT_HTTP_PROXY"'
assert_contains "$http_proxy_flow_body" 'activate_http_proxy ""'

printf 'Miyoo proxy status refresh tests passed\n'
