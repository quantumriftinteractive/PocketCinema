#!/bin/sh

# Connection-profile helpers own only PocketStremio endpoint and generic-proxy
# configuration. They deliberately know nothing about the software supplying a
# proxy or any network-provider lifecycle.

POCKETSTREMIO_CONNECTION_AUTOMATIC="automatic"
POCKETSTREMIO_CONNECTION_LOCAL="local"
POCKETSTREMIO_CONNECTION_REMOTE="remote"

pocketstremio_normalize_pss_url() {
  pss_url=$(printf '%s' "$1" | tr -d '\r\n')
  [ -n "$pss_url" ] || return 1
  case "$pss_url" in
    *[[:space:]]*|*'@'*|*'?'*|*'#'*) return 1 ;;
    http://*|https://*) ;;
    *://*) return 1 ;;
    *) pss_url="http://$pss_url" ;;
  esac
  case "$pss_url" in
    http://*/|https://*/)
      pss_url=${pss_url%/}
      ;;
  esac
  pss_endpoint=${pss_url#http://}
  [ "$pss_endpoint" = "$pss_url" ] && pss_endpoint=${pss_url#https://}
  case "$pss_endpoint" in
    ''|/*|*'/'*) return 1 ;;
  esac
  printf '%s\n' "$pss_url"
}

pocketstremio_normalize_connection_mode() {
  case "$1" in
    "$POCKETSTREMIO_CONNECTION_AUTOMATIC"|"$POCKETSTREMIO_CONNECTION_LOCAL"|"$POCKETSTREMIO_CONNECTION_REMOTE")
      printf '%s\n' "$1"
      ;;
    *) return 1 ;;
  esac
}

pocketstremio_validate_connection_profile() {
  profile_local="$1"
  profile_remote="$2"
  profile_mode="$3"
  profile_proxy="$4"

  [ -z "$profile_local" ] || pocketstremio_normalize_pss_url "$profile_local" >/dev/null || return 1
  [ -z "$profile_remote" ] || pocketstremio_normalize_pss_url "$profile_remote" >/dev/null || return 1
  pocketstremio_normalize_connection_mode "$profile_mode" >/dev/null || return 1
  [ -n "$profile_local$profile_remote" ] || return 1
  if [ -n "$profile_proxy" ]; then
    pocketstremio_normalize_http_proxy "$profile_proxy" >/dev/null || return 1
  fi
  case "$profile_mode" in
    "$POCKETSTREMIO_CONNECTION_LOCAL") [ -n "$profile_local" ] ;;
    "$POCKETSTREMIO_CONNECTION_REMOTE") [ -n "$profile_remote" ] ;;
    *) return 0 ;;
  esac
}

pocketstremio_save_connection_profile() {
  profile_config_file="$1"
  profile_local="$2"
  profile_remote="$3"
  profile_mode="$4"
  profile_proxy="$5"
  profile_config_dir=$(dirname "$profile_config_file")
  profile_config_temp="$profile_config_file.tmp"

  pocketstremio_validate_connection_profile "$profile_local" "$profile_remote" \
    "$profile_mode" "$profile_proxy" || return 1
  if [ -n "$profile_local" ]; then
    profile_local=$(pocketstremio_normalize_pss_url "$profile_local") || return 1
  fi
  if [ -n "$profile_remote" ]; then
    profile_remote=$(pocketstremio_normalize_pss_url "$profile_remote") || return 1
  fi
  if [ -n "$profile_proxy" ]; then
    profile_proxy=$(pocketstremio_normalize_http_proxy "$profile_proxy") || return 1
  fi
  mkdir -p "$profile_config_dir" || return 1
  if [ -f "$profile_config_file" ]; then
    cp "$profile_config_file" "$profile_config_file.bak" || return 1
  fi
  awk -v local_pss="$profile_local" -v remote_pss="$profile_remote" \
    -v mode="$profile_mode" -v proxy="$profile_proxy" '
    BEGIN { local_seen = remote_seen = mode_seen = proxy_seen = 0 }
    /^LOCAL_PSS=/ {
      if (!local_seen) print "LOCAL_PSS=" local_pss
      local_seen = 1
      next
    }
    /^REMOTE_PSS=/ {
      if (!remote_seen) print "REMOTE_PSS=" remote_pss
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
      if (!local_seen) print "LOCAL_PSS=" local_pss
      if (!remote_seen) print "REMOTE_PSS=" remote_pss
      if (!mode_seen) print "CONNECTION_MODE=" mode
      if (!proxy_seen) print "PROXY=" proxy
    }
  ' "$profile_config_file" 2>/dev/null >"$profile_config_temp" || {
    printf 'LOCAL_PSS=%s\nREMOTE_PSS=%s\nCONNECTION_MODE=%s\nPROXY=%s\n' \
      "$profile_local" "$profile_remote" "$profile_mode" "$profile_proxy" \
      >"$profile_config_temp" || return 1
  }
  mv "$profile_config_temp" "$profile_config_file" || return 1
  chmod 644 "$profile_config_file"
}

# The caller supplies pocketstremio_probe_route <route> <url> <proxy> and sets
# POCKETSTREMIO_ROUTE_PROBE_FAILURE on failure. Keeping the ordering here makes
# every PSS request path depend on one resolved active route.
pocketstremio_resolve_connection_route() {
  resolve_mode="$1"
  resolve_local="$2"
  resolve_remote="$3"
  resolve_proxy="$4"
  resolve_legacy_server="$5"
  resolve_legacy_proxy="$6"
  POCKETSTREMIO_RESOLVED_ROUTE=""
  POCKETSTREMIO_RESOLVED_SERVER=""
  POCKETSTREMIO_RESOLVED_PROXY=""
  POCKETSTREMIO_ROUTE_FAILURE=""

  if [ "$resolve_mode" = legacy ]; then
    pocketstremio_probe_route legacy "$resolve_legacy_server" "$resolve_legacy_proxy" || {
      POCKETSTREMIO_ROUTE_FAILURE="legacy_pss_unreachable"
      return 1
    }
    POCKETSTREMIO_RESOLVED_ROUTE=legacy
    POCKETSTREMIO_RESOLVED_SERVER="$resolve_legacy_server"
    POCKETSTREMIO_RESOLVED_PROXY="$resolve_legacy_proxy"
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
    *) POCKETSTREMIO_ROUTE_FAILURE="no_pss_connection"; return 1 ;;
  esac
  if [ "$resolve_try_local" -eq 1 ]; then
    if pocketstremio_probe_route local "$resolve_local" ""; then
      POCKETSTREMIO_RESOLVED_ROUTE=local
      POCKETSTREMIO_RESOLVED_SERVER="$resolve_local"
      return 0
    fi
    POCKETSTREMIO_ROUTE_FAILURE="local_pss_unreachable"
  fi
  if [ "$resolve_try_remote" -eq 1 ]; then
    if [ -z "$resolve_proxy" ]; then
      POCKETSTREMIO_ROUTE_FAILURE="remote_proxy_unavailable"
      return 1
    fi
    if pocketstremio_probe_route remote "$resolve_remote" "$resolve_proxy"; then
      POCKETSTREMIO_RESOLVED_ROUTE=remote
      POCKETSTREMIO_RESOLVED_SERVER="$resolve_remote"
      POCKETSTREMIO_RESOLVED_PROXY="$resolve_proxy"
      return 0
    fi
    case "${POCKETSTREMIO_ROUTE_PROBE_FAILURE:-}" in
      proxy) POCKETSTREMIO_ROUTE_FAILURE="remote_proxy_unavailable" ;;
      *) POCKETSTREMIO_ROUTE_FAILURE="remote_pss_unreachable" ;;
    esac
    return 1
  fi
  POCKETSTREMIO_ROUTE_FAILURE="no_pss_connection"
  return 1
}
