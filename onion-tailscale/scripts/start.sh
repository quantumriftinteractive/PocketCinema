#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/common.sh"
. "$SCRIPT_DIR/proxy-listeners.sh"

LOG_FILE="$LOG_DIR/tailscaled.log"

mkdir -p "$STATE_DIR" "$LOG_DIR" "$RUN_DIR"

if [ ! -x "$TAILSCALED" ]; then
  echo "Missing executable: $TAILSCALED"
  echo "Install the ARM static Tailscale binaries into $BASE_DIR/bin first."
  exit 1
fi

EXISTING_PID=$(managed_pid || true)
if [ -n "$EXISTING_PID" ]; then
  echo "tailscaled is already running with PID $EXISTING_PID"
  exit 0
fi

if [ -f "$PID_FILE" ]; then
  echo "Removing stale or unrelated PID file"
  rm -f "$PID_FILE"
fi

OTHER_PID=$(other_tailscaled_pid || true)
if [ -n "$OTHER_PID" ]; then
  echo "Another tailscaled process is running with PID $OTHER_PID."
  echo "Stop or migrate that daemon before enabling this app."
  exit 2
fi

rm -f "$SOCKET_FILE"

HOME="$RUN_DIR" TS_NO_LOGS_NO_SUPPORT="${TS_NO_LOGS_NO_SUPPORT:-true}" nohup "$TAILSCALED" \
  --tun=userspace-networking \
  --state="$STATE_FILE" \
  --socket="$SOCKET_FILE" \
  --socks5-server="$SOCKS5_LISTEN" \
  --outbound-http-proxy-listen="$HTTP_PROXY_LISTEN" \
  >>"$LOG_FILE" 2>&1 &

PID=$!
echo "$PID" >"$PID_FILE"

attempt=0
while [ "$attempt" -lt 8 ] && kill -0 "$PID" 2>/dev/null && [ ! -S "$SOCKET_FILE" ]; do
  attempt=$((attempt + 1))
  sleep 1
done

if kill -0 "$PID" 2>/dev/null && [ -S "$SOCKET_FILE" ]; then
  echo "tailscaled started with PID $PID"
  echo "socket: $SOCKET_FILE"
  echo "SOCKS5 proxy: $SOCKS5_LISTEN"
  echo "HTTP proxy: $HTTP_PROXY_LISTEN"
  echo "log: $LOG_FILE"
else
  if kill -0 "$PID" 2>/dev/null; then
    kill "$PID" 2>/dev/null || true
    sleep 1
    kill -9 "$PID" 2>/dev/null || true
  fi
  rm -f "$PID_FILE" "$SOCKET_FILE"
  echo "tailscaled failed to stay running. Last log lines:"
  tail -n 40 "$LOG_FILE" 2>/dev/null || true
  exit 1
fi
