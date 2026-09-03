#!/bin/sh
set -u

BASE_DIR=/mnt/SDCARD/App/Tailscale
SYS_DIR=/mnt/SDCARD/.tmp_update
LOG_DIR="$BASE_DIR/logs"
LOG_FILE="$LOG_DIR/app.log"
SELECTOR="$BASE_DIR/bin/onion-tailscale-selector"
INFOPANEL="$SYS_DIR/bin/infoPanel"
ADMIN_URL="https://login.tailscale.com/admin/machines"

mkdir -p "$LOG_DIR"
. "$BASE_DIR/scripts/proxy-listeners.sh"

log() {
  printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >>"$LOG_FILE"
}

show_message() {
  body="$1"
  log "message=$body"
  if [ -x "$INFOPANEL" ]; then
    "$INFOPANEL" --title "Tailscale" --message "$body" --auto >/dev/null 2>&1 || true
  else
    printf 'Tailscale: %s\n' "$body"
  fi
}

select_action() {
  title="$1"
  bottom="$2"
  menu_file="$3"
  ONION_TAILSCALE_SELECTOR_LOG="$LOG_FILE" \
    "$SELECTOR" --menu-qr "$ADMIN_URL" "$title" "$bottom" \
    <"$menu_file" 2>>"$LOG_FILE"
}

show_login_qr() {
  login_url_value="$1"
  printf '%s\n' "$login_url_value" | ONION_TAILSCALE_SELECTOR_LOG="$LOG_FILE" \
    "$SELECTOR" --qr "Connect Tailscale" "Scan, approve, A Refresh, B Back" 2>>"$LOG_FILE"
}

connect_account() {
  login_result=$("$BASE_DIR/scripts/login.sh" start 2>>"$LOG_FILE")
  login_rc=$?
  if [ "$login_rc" -ne 0 ]; then
    show_message "Could not create a verification URL."
    return 1
  fi
  if [ "$login_result" = "connected" ]; then
    show_message "Tailscale account connected"
    return 0
  fi

  while :; do
    login_action=$(show_login_qr "$login_result")
    login_selector_rc=$?
    [ "$login_selector_rc" -eq 0 ] || break
    case "$login_action" in
      refresh)
        login_status=$("$BASE_DIR/scripts/login.sh" status 2>>"$LOG_FILE")
        if [ "$login_status" = "connected" ]; then
          show_message "Tailscale account connected"
          rm -f /tmp/onion-tailscale-login-menu
          return 0
        fi
        case "$login_status" in
          https://*) login_result="$login_status" ;;
        esac
        ;;
    esac
  done
  rm -f /tmp/onion-tailscale-login-menu
  return 0
}

if [ ! -x "$SELECTOR" ]; then
  show_message "Controller UI is missing. Check app installation."
  exit 1
fi

log "Tailscale app launch"
cd "$SYS_DIR" || exit 1
unset LD_PRELOAD

while :; do
  status_line=$("$BASE_DIR/scripts/status.sh" --brief 2>>"$LOG_FILE")
  service_state=$(printf '%s' "$status_line" | cut -f1)
  tailscale_ip=$(printf '%s' "$status_line" | cut -f2)
  autostart_state=$("$BASE_DIR/scripts/autostart.sh" status 2>>"$LOG_FILE")

  if [ "$service_state" = "enabled" ]; then
    title="Tailscale: Enabled"
    [ -n "$tailscale_ip" ] || tailscale_ip="unavailable"
    bottom="IP $tailscale_ip  HTTP proxy: $HTTP_PROXY_LISTEN"
    if [ "$tailscale_ip" = "unavailable" ]; then
      printf 'Connect account\nDisable\nAutomatic enable: %s\nRefresh\nExit\n' "$autostart_state" >/tmp/onion-tailscale-menu
    else
      printf 'Disable\nAutomatic enable: %s\nRefresh\nExit\n' "$autostart_state" >/tmp/onion-tailscale-menu
    fi
  else
    title="Tailscale: Disabled"
    bottom="IP unavailable  HTTP proxy: $HTTP_PROXY_LISTEN"
    printf 'Enable\nAutomatic enable: %s\nRefresh\nExit\n' "$autostart_state" > /tmp/onion-tailscale-menu
  fi

  action=$(select_action "$title" "$bottom" /tmp/onion-tailscale-menu)
  selector_rc=$?
  log "selector rc=$selector_rc action=${action:-none} state=$service_state ip=${tailscale_ip:-none} autostart=$autostart_state"
  [ "$selector_rc" -eq 0 ] || break

  case "$action" in
    Enable)
      if "$BASE_DIR/scripts/start.sh" >>"$LOG_FILE" 2>&1; then
        show_message "Tailscale enabled"
      else
        show_message "Enable failed. Check Tailscale logs."
      fi
      ;;
    "Connect account")
      connect_account
      ;;
    Disable)
      if "$BASE_DIR/scripts/stop.sh" >>"$LOG_FILE" 2>&1; then
        show_message "Tailscale disabled"
      else
        show_message "Disable failed. Check Tailscale logs."
      fi
      ;;
    "Automatic enable: enabled")
      if "$BASE_DIR/scripts/autostart.sh" disable >>"$LOG_FILE" 2>&1; then
        show_message "Automatic enable is off"
      else
        show_message "Autostart change failed"
      fi
      ;;
    "Automatic enable: disabled")
      if "$BASE_DIR/scripts/autostart.sh" enable >>"$LOG_FILE" 2>&1; then
        show_message "Automatic enable is on"
      else
        show_message "Autostart change failed"
      fi
      ;;
    "Automatic enable: conflict")
      show_message "Startup hook conflict. No file was changed."
      ;;
    Refresh)
      log "status refresh"
      ;;
    Exit)
      break
      ;;
  esac
done

rm -f /tmp/onion-tailscale-menu /tmp/onion-tailscale-login-menu
log "Tailscale app exit"
exit 0
