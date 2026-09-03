#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
UI_SCRIPT="$SCRIPT_DIR/../client/miyoo/pocketcinema-ui.sh"

assert_contains() {
  printf '%s\n' "$1" | grep -F -q -- "$2" || {
    printf 'expected [%s] in proxy status-refresh path\n' "$2" >&2
    exit 1
  }
}

assert_not_contains() {
  if printf '%s\n' "$1" | grep -F -q -- "$2"; then
    printf 'did not expect [%s] in proxy status-refresh path\n' "$2" >&2
    exit 1
  fi
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
resolve_active_route_body=$(awk '
  /^resolve_active_route\(\)/ { active = 1 }
  active { print }
  active && /^}/ { exit }
' "$UI_SCRIPT")
http_proxy_flow_body=$(awk '
  /^http_proxy_flow\(\)/ { active = 1 }
  active { print }
  active && /^}/ { exit }
' "$UI_SCRIPT")
enabled_proxy_menu=$(printf '%s\n' "$http_proxy_flow_body" | awk '
  /if \[ -n "\$PROXY" \]; then/ { active = 1; next }
  active && /^    else$/ { exit }
  active { print }
')
disabled_proxy_menu=$(printf '%s\n' "$http_proxy_flow_body" | awk '
  /if \[ -n "\$PROXY" \]; then/ { branch = 1; next }
  branch == 1 && /^    else$/ { branch = 2; next }
  branch == 2 && /^    fi$/ { exit }
  branch == 2 { print }
')

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

# The reused monitor invalidates stale state, then one shared route resolver
# performs the normal status validation with the selected transport.
assert_contains "$start_server_monitor_body" 'write_server_status "Server: Connecting..."'
assert_contains "$start_server_monitor_body" 'resolve_active_route'
assert_contains "$resolve_active_route_body" 'pocketcinema_resolve_connection_route'

# A disabled proxy offers an explicit activation action, not a redundant
# disable action. Edit, default activation/restore, and disable all share
# activate_http_proxy.
assert_contains "$http_proxy_flow_body" 'if [ -n "$PROXY" ]; then'
assert_contains "$enabled_proxy_menu" 'Disable proxy'
assert_contains "$disabled_proxy_menu" 'Enable default (%s)'
assert_not_contains "$disabled_proxy_menu" 'Disable proxy'
assert_contains "$http_proxy_flow_body" 'activate_http_proxy "$normalized_proxy"'
assert_contains "$http_proxy_flow_body" 'activate_http_proxy "$POCKETCINEMA_DEFAULT_HTTP_PROXY"'
assert_contains "$http_proxy_flow_body" 'activate_http_proxy ""'

printf 'Miyoo proxy status refresh tests passed\n'
