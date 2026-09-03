#!/bin/sh

# PocketStremio's supported generic HTTP-proxy default. It is a user-owned
# setting only; this file does not identify or manage the software providing it.
POCKETSTREMIO_DEFAULT_HTTP_PROXY="http://127.0.0.1:1055"

pocketstremio_normalize_http_proxy() {
  proxy_value=$(printf '%s' "$1" | tr -d '\r\n')
  [ -n "$proxy_value" ] || return 1
  case "$proxy_value" in
    *[[:space:]]*|*'?'*|*'%'*|*'@'*) return 1 ;;
    http://*)
      proxy_endpoint=${proxy_value#http://}
      # Legacy configs were passed straight to curl, which accepts the
      # conventional root-path spelling. Canonicalize only that one harmless
      # trailing slash; non-root paths remain unsupported.
      case "$proxy_endpoint" in
        */) proxy_endpoint=${proxy_endpoint%/} ;;
      esac
      ;;
    *://*) return 1 ;;
    *) proxy_endpoint=$proxy_value ;;
  esac

  case "$proxy_endpoint" in
    ''|:*|*:*:*|*'/'*) return 1 ;;
  esac
  proxy_host=${proxy_endpoint%:*}
  proxy_port=${proxy_endpoint##*:}
  [ "$proxy_host" != "$proxy_endpoint" ] || return 1
  case "$proxy_host" in
    ''|.*|*.|*..*|*[!A-Za-z0-9.-]*) return 1 ;;
  esac
  case "$proxy_port" in
    ''|*[!0-9]*) return 1 ;;
  esac
  proxy_port_numeric=$(printf '%s' "$proxy_port" | sed 's/^0*//')
  [ -n "$proxy_port_numeric" ] || proxy_port_numeric=0
  [ "${#proxy_port_numeric}" -le 5 ] || return 1
  [ "$proxy_port_numeric" -ge 1 ] 2>/dev/null || return 1
  [ "$proxy_port_numeric" -le 65535 ] 2>/dev/null || return 1
  printf 'http://%s:%s\n' "$proxy_host" "$proxy_port"
}

pocketstremio_save_http_proxy() {
  proxy_config_file="$1"
  proxy_value="$2"
  proxy_config_dir=$(dirname "$proxy_config_file")
  proxy_config_temp="$proxy_config_file.tmp"
  mkdir -p "$proxy_config_dir" || return 1
  if [ -f "$proxy_config_file" ]; then
    cp "$proxy_config_file" "$proxy_config_file.bak" || return 1
  fi
  awk -v proxy="$proxy_value" '
    BEGIN { replaced = 0 }
    /^PROXY=/ {
      if (!replaced) {
        print "PROXY=" proxy
        replaced = 1
      }
      next
    }
    { print }
    END {
      if (!replaced) print "PROXY=" proxy
    }
  ' "$proxy_config_file" 2>/dev/null >"$proxy_config_temp" || {
    printf 'PROXY=%s\n' "$proxy_value" >"$proxy_config_temp" || return 1
  }
  mv "$proxy_config_temp" "$proxy_config_file" || return 1
  chmod 644 "$proxy_config_file"
}
