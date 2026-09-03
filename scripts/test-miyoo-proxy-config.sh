#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/../client/miyoo/pocketstremio-proxy.sh"

test_root=$(mktemp -d "${TMPDIR:-/tmp}/pocketstremio-proxy-test.XXXXXX")
trap 'rm -rf "$test_root"' EXIT HUP INT TERM
test_config="$test_root/pocketstremio.conf"

assert_equal() {
  [ "$1" = "$2" ] || {
    printf 'expected [%s], got [%s]\n' "$2" "$1" >&2
    exit 1
  }
}

assert_invalid() {
  if pocketstremio_normalize_http_proxy "$1" >/dev/null 2>&1; then
    printf 'expected invalid proxy: %s\n' "$1" >&2
    exit 1
  fi
}

assert_equal "$POCKETSTREMIO_DEFAULT_HTTP_PROXY" "http://127.0.0.1:1055"
assert_equal "$(pocketstremio_normalize_http_proxy 127.0.0.1:1055)" \
  "http://127.0.0.1:1055"
assert_equal "$(pocketstremio_normalize_http_proxy http://proxy.example:8080)" \
  "http://proxy.example:8080"
for invalid_proxy in '' 'http://:1055' '127.0.0.1' '127.0.0.1:0' \
  '127.0.0.1:65536' 'https://127.0.0.1:1055' 'http://user@127.0.0.1:1055' \
  'http://127.0.0.1:1055/path' '127.0.0.1:10 55'; do
  assert_invalid "$invalid_proxy"
done

cat >"$test_config" <<'EOF'
SERVER_BASE=http://192.0.2.1:8755
PROXY=http://existing.example:8080
AUDIO_GAIN=2.0
EOF
pocketstremio_save_http_proxy "$test_config" "http://127.0.0.1:2060"
assert_equal "$(sed -n '1p' "$test_config")" "SERVER_BASE=http://192.0.2.1:8755"
assert_equal "$(sed -n '2p' "$test_config")" "PROXY=http://127.0.0.1:2060"
assert_equal "$(sed -n '3p' "$test_config")" "AUDIO_GAIN=2.0"
pocketstremio_save_http_proxy "$test_config" ""
assert_equal "$(sed -n '2p' "$test_config")" "PROXY="
pocketstremio_save_http_proxy "$test_config" "$POCKETSTREMIO_DEFAULT_HTTP_PROXY"
assert_equal "$(sed -n '2p' "$test_config")" "PROXY=http://127.0.0.1:1055"

printf 'Miyoo proxy configuration tests passed\n'
