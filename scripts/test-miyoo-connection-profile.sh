#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/../client/miyoo/pocketstremio-proxy.sh"
. "$SCRIPT_DIR/../client/miyoo/pocketstremio-connection.sh"
UI_SCRIPT="$SCRIPT_DIR/../client/miyoo/pocketstremio-ui.sh"

test_root=$(mktemp -d "${TMPDIR:-/tmp}/pocketstremio-connection-test.XXXXXX")
trap 'rm -rf "$test_root"' EXIT HUP INT TERM
test_config="$test_root/pocketstremio.conf"

assert_equal() {
  [ "$1" = "$2" ] || {
    printf 'expected [%s], got [%s]\n' "$2" "$1" >&2
    exit 1
  }
}

probe_log=""
probe_local=fail
probe_remote=fail
probe_remote_failure=pss
pocketstremio_probe_route() {
  probe_log="${probe_log}${1}:${3:-direct}|"
  case "$1" in
    local) [ "$probe_local" = ok ] ;;
    remote)
      [ "$probe_remote" = ok ] || POCKETSTREMIO_ROUTE_PROBE_FAILURE="$probe_remote_failure"
      [ "$probe_remote" = ok ]
      ;;
    legacy) [ "$probe_local" = ok ] ;;
  esac
}

assert_invalid_profile() {
  if pocketstremio_validate_connection_profile "$1" "$2" "$3" "$4"; then
    printf 'expected invalid profile\n' >&2
    exit 1
  fi
}

assert_ui_contains() {
  grep -F -q -- "$1" "$UI_SCRIPT" || {
    printf 'expected [%s] in Miyoo connection UI\n' "$1" >&2
    exit 1
  }
}

assert_ui_count() {
  actual_count=$(grep -F -c -- "$1" "$UI_SCRIPT")
  assert_equal "$actual_count" "$2"
}

assert_equal "$(pocketstremio_normalize_pss_url 192.0.2.4:8755)" "http://192.0.2.4:8755"
assert_equal "$(pocketstremio_normalize_pss_url http://192.0.2.4:8755/)" "http://192.0.2.4:8755"
assert_equal "$(pocketstremio_normalize_connection_mode automatic)" automatic
assert_invalid_profile "" "" automatic ""
assert_invalid_profile "http://192.0.2.4:8755" "" remote ""
assert_invalid_profile "http://user@192.0.2.4:8755" "" local ""
if ! pocketstremio_validate_connection_profile "" "http://100.64.0.4:8755" remote ""; then
  printf 'disabled remote proxy profile should remain loadable\n' >&2
  exit 1
fi

cat >"$test_config" <<'EOF'
SERVER_BASE=http://100.64.0.4:8755
PROXY=http://127.0.0.1:1055
AUDIO_GAIN=2.0
EOF
pocketstremio_save_connection_profile "$test_config" "http://192.0.2.4:8755" \
  "100.64.0.4:8755" automatic "127.0.0.1:1055"
assert_equal "$(sed -n '1p' "$test_config")" "SERVER_BASE=http://100.64.0.4:8755"
assert_equal "$(sed -n '2p' "$test_config")" "PROXY=http://127.0.0.1:1055"
assert_equal "$(sed -n '3p' "$test_config")" "AUDIO_GAIN=2.0"
assert_equal "$(sed -n '4p' "$test_config")" "LOCAL_PSS=http://192.0.2.4:8755"
assert_equal "$(sed -n '5p' "$test_config")" "REMOTE_PSS=http://100.64.0.4:8755"
assert_equal "$(sed -n '6p' "$test_config")" "CONNECTION_MODE=automatic"
before_failure=$(cksum "$test_config")
if pocketstremio_save_connection_profile "$test_config" "" "" automatic ""; then
  printf 'invalid profile was saved\n' >&2
  exit 1
fi
assert_equal "$(cksum "$test_config")" "$before_failure"
rm -f "$test_config"
pocketstremio_save_connection_profile "$test_config" "http://192.0.2.4:8755" \
  "" local ""
assert_equal "$(sed -n '1p' "$test_config")" "LOCAL_PSS=http://192.0.2.4:8755"
assert_equal "$(sed -n '2p' "$test_config")" "REMOTE_PSS="
assert_equal "$(sed -n '3p' "$test_config")" "CONNECTION_MODE=local"
assert_equal "$(sed -n '4p' "$test_config")" "PROXY="

# Automatic tries Local directly before Remote; every other mode is isolated.
probe_local=ok probe_remote=ok probe_log=""
pocketstremio_resolve_connection_route automatic http://lan:8755 http://tail:8755 \
  http://127.0.0.1:1055 "" ""
assert_equal "$POCKETSTREMIO_RESOLVED_ROUTE" local
assert_equal "$POCKETSTREMIO_RESOLVED_PROXY" ""
assert_equal "$probe_log" 'local:direct|'
probe_local=fail probe_remote=ok probe_log=""
pocketstremio_resolve_connection_route automatic http://lan:8755 http://tail:8755 \
  http://127.0.0.1:1055 "" ""
assert_equal "$POCKETSTREMIO_RESOLVED_ROUTE" remote
assert_equal "$POCKETSTREMIO_RESOLVED_PROXY" http://127.0.0.1:1055
assert_equal "$probe_log" 'local:direct|remote:http://127.0.0.1:1055|'
probe_local=fail probe_remote=fail probe_remote_failure=proxy probe_log=""
if pocketstremio_resolve_connection_route automatic http://lan:8755 http://tail:8755 \
  http://127.0.0.1:1055 "" ""; then
  printf 'automatic should fail when both routes fail\n' >&2
  exit 1
fi
assert_equal "$POCKETSTREMIO_ROUTE_FAILURE" remote_proxy_unavailable
probe_local=fail probe_remote=ok probe_log=""
if pocketstremio_resolve_connection_route local http://lan:8755 http://tail:8755 \
  http://127.0.0.1:1055 "" ""; then
  printf 'local mode should not fall back to remote\n' >&2
  exit 1
fi
assert_equal "$probe_log" 'local:direct|'
probe_local=ok probe_remote=ok probe_log=""
pocketstremio_resolve_connection_route remote http://lan:8755 http://tail:8755 \
  http://127.0.0.1:1055 "" ""
assert_equal "$POCKETSTREMIO_RESOLVED_ROUTE" remote
assert_equal "$probe_log" 'remote:http://127.0.0.1:1055|'
probe_log=""
if pocketstremio_resolve_connection_route remote "" http://tail:8755 "" "" ""; then
  printf 'remote mode should fail without a proxy\n' >&2
  exit 1
fi
assert_equal "$POCKETSTREMIO_ROUTE_FAILURE" remote_proxy_unavailable

# Discovery is explicitly only a found candidate until direct validation; the
# remote setup has a manual endpoint path and never invokes discovery.
assert_ui_contains 'Found but local PSS unreachable'
assert_ui_contains 'validate_pss_url_with_proxy "$discovered_url" ""'
assert_ui_contains 'read_setup_pss_url "$REMOTE_PSS" "Remote PSS URL"'
assert_ui_contains 'pocketstremio_save_connection_profile "$CONFIG_FILE"'
assert_ui_contains 'start_server_monitor'
assert_ui_contains 'ensure_active_route()'
assert_ui_count 'ensure_active_route || return 1' 5

printf 'Miyoo connection profile tests passed\n'
