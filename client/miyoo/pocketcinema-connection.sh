#!/bin/sh

# Connection-profile helpers own only PocketCinema endpoint and generic-proxy
# configuration. They deliberately know nothing about the software supplying a
# proxy or any network-provider lifecycle.

POCKETCINEMA_CONNECTION_AUTOMATIC="automatic"
POCKETCINEMA_CONNECTION_LOCAL="local"
POCKETCINEMA_CONNECTION_REMOTE="remote"

pocketcinema_normalize_pcserver_url() {
  pcserver_url=$(printf '%s' "$1" | tr -d '\r\n')
  [ -n "$pcserver_url" ] || return 1
  case "$pcserver_url" in
    *[[:space:]]*|*'@'*|*'?'*|*'#'*) return 1 ;;
    http://*|https://*) ;;
    *://*) return 1 ;;
    *) pcserver_url="http://$pcserver_url" ;;
  esac
  case "$pcserver_url" in
    http://*/|https://*/)
      pcserver_url=${pcserver_url%/}
      ;;
  esac
  pcserver_endpoint=${pcserver_url#http://}
  [ "$pcserver_endpoint" = "$pcserver_url" ] && pcserver_endpoint=${pcserver_url#https://}
  case "$pcserver_endpoint" in
    ''|/*|*'/'*) return 1 ;;
  esac
  printf '%s\n' "$pcserver_url"
}

pocketcinema_normalize_connection_mode() {
  case "$1" in
    "$POCKETCINEMA_CONNECTION_AUTOMATIC"|"$POCKETCINEMA_CONNECTION_LOCAL"|"$POCKETCINEMA_CONNECTION_REMOTE")
      printf '%s\n' "$1"
      ;;
    *) return 1 ;;
  esac
}

pocketcinema_validate_connection_profile() {
  profile_local="$1"
  profile_remote="$2"
  profile_mode="$3"
  profile_proxy="$4"

  [ -z "$profile_local" ] || pocketcinema_normalize_pcserver_url "$profile_local" >/dev/null || return 1
  [ -z "$profile_remote" ] || pocketcinema_normalize_pcserver_url "$profile_remote" >/dev/null || return 1
  pocketcinema_normalize_connection_mode "$profile_mode" >/dev/null || return 1
  [ -n "$profile_local$profile_remote" ] || return 1
  if [ -n "$profile_proxy" ]; then
    pocketcinema_normalize_http_proxy "$profile_proxy" >/dev/null || return 1
  fi
  case "$profile_mode" in
    "$POCKETCINEMA_CONNECTION_LOCAL") [ -n "$profile_local" ] ;;
    "$POCKETCINEMA_CONNECTION_REMOTE") [ -n "$profile_remote" ] ;;
    *) return 0 ;;
  esac
}

pocketcinema_save_connection_profile() {
  profile_config_file="$1"
  profile_local="$2"
  profile_remote="$3"
  profile_mode="$4"
  profile_proxy="$5"
  profile_config_dir=$(dirname "$profile_config_file")
  profile_config_temp="$profile_config_file.tmp"

  pocketcinema_validate_connection_profile "$profile_local" "$profile_remote" \
    "$profile_mode" "$profile_proxy" || return 1
  if [ -n "$profile_local" ]; then
    profile_local=$(pocketcinema_normalize_pcserver_url "$profile_local") || return 1
  fi
  if [ -n "$profile_remote" ]; then
    profile_remote=$(pocketcinema_normalize_pcserver_url "$profile_remote") || return 1
  fi
  if [ -n "$profile_proxy" ]; then
    profile_proxy=$(pocketcinema_normalize_http_proxy "$profile_proxy") || return 1
  fi
  mkdir -p "$profile_config_dir" || return 1
  if [ -f "$profile_config_file" ]; then
    cp "$profile_config_file" "$profile_config_file.bak" || return 1
  fi
  awk -v local_pcserver="$profile_local" -v remote_pcserver="$profile_remote" \
    -v mode="$profile_mode" -v proxy="$profile_proxy" '
    BEGIN { local_seen = remote_seen = mode_seen = proxy_seen = 0 }
    /^LOCAL_PCSERVER=/ {
      if (!local_seen) print "LOCAL_PCSERVER=" local_pcserver
      local_seen = 1
      next
    }
    /^REMOTE_PCSERVER=/ {
      if (!remote_seen) print "REMOTE_PCSERVER=" remote_pcserver
      remote_seen = 1
      next
    }
    /^CONNECTION_MODE=/ {
      if (!mode_seen) print "CONNECTION_MODE=" mode
      mode_seen = 1
      next
    }
    /^PROXY=/ {
      if (!proxy_seen) print "PROXY=" proxy
      proxy_seen = 1
      next
    }
    { print }
    END {
      if (!local_seen) print "LOCAL_PCSERVER=" local_pcserver
      if (!remote_seen) print "REMOTE_PCSERVER=" remote_pcserver
      if (!mode_seen) print "CONNECTION_MODE=" mode
      if (!proxy_seen) print "PROXY=" proxy
    }
  ' "$profile_config_file" 2>/dev/null >"$profile_config_temp" || {
    printf 'LOCAL_PCSERVER=%s\nREMOTE_PCSERVER=%s\nCONNECTION_MODE=%s\nPROXY=%s\n' \
      "$profile_local" "$profile_remote" "$profile_mode" "$profile_proxy" \
      >"$profile_config_temp" || return 1
  }
  mv "$profile_config_temp" "$profile_config_file" || return 1
  chmod 644 "$profile_config_file"
}

# The caller supplies pocketcinema_probe_route <route> <url> <proxy> and sets
# POCKETCINEMA_ROUTE_PROBE_FAILURE on failure. Keeping the ordering here makes
# every PCServer request path depend on one resolved active route.
pocketcinema_resolve_connection_route() {
  resolve_mode="$1"
  resolve_local="$2"
  resolve_remote="$3"
  resolve_proxy="$4"
  resolve_legacy_server="$5"
  resolve_legacy_proxy="$6"
  POCKETCINEMA_RESOLVED_ROUTE=""
  POCKETCINEMA_RESOLVED_SERVER=""
  POCKETCINEMA_RESOLVED_PROXY=""
  POCKETCINEMA_ROUTE_FAILURE=""

  if [ "$resolve_mode" = legacy ]; then
    pocketcinema_probe_route legacy "$resolve_legacy_server" "$resolve_legacy_proxy" || {
      POCKETCINEMA_ROUTE_FAILURE="legacy_pcserver_unreachable"
      return 1
    }
    POCKETCINEMA_RESOLVED_ROUTE=legacy
    POCKETCINEMA_RESOLVED_SERVER="$resolve_legacy_server"
    POCKETCINEMA_RESOLVED_PROXY="$resolve_legacy_proxy"
    return 0
  fi

  resolve_try_local=0
  resolve_try_remote=0
  case "$resolve_mode" in
    automatic)
      [ -n "$resolve_local" ] && resolve_try_local=1
      [ -n "$resolve_remote" ] && resolve_try_remote=1
      ;;
    local) resolve_try_local=1 ;;
    remote) resolve_try_remote=1 ;;
    *) POCKETCINEMA_ROUTE_FAILURE="no_pcserver_connection"; return 1 ;;
  esac
  if [ "$resolve_try_local" -eq 1 ]; then
    if pocketcinema_probe_route local "$resolve_local" ""; then
      POCKETCINEMA_RESOLVED_ROUTE=local
      POCKETCINEMA_RESOLVED_SERVER="$resolve_local"
      return 0
    fi
    POCKETCINEMA_ROUTE_FAILURE="local_pcserver_unreachable"
  fi
  if [ "$resolve_try_remote" -eq 1 ]; then
    if [ -z "$resolve_proxy" ]; then
      POCKETCINEMA_ROUTE_FAILURE="remote_proxy_unavailable"
      return 1
    fi
    if pocketcinema_probe_route remote "$resolve_remote" "$resolve_proxy"; then
      POCKETCINEMA_RESOLVED_ROUTE=remote
      POCKETCINEMA_RESOLVED_SERVER="$resolve_remote"
      POCKETCINEMA_RESOLVED_PROXY="$resolve_proxy"
      return 0
    fi
    case "${POCKETCINEMA_ROUTE_PROBE_FAILURE:-}" in
      proxy) POCKETCINEMA_ROUTE_FAILURE="remote_proxy_unavailable" ;;
      *) POCKETCINEMA_ROUTE_FAILURE="remote_pcserver_unreachable" ;;
    esac
    return 1
  fi
  POCKETCINEMA_ROUTE_FAILURE="no_pcserver_connection"
  return 1
}
