#!/system/bin/sh

MODDIR=${0%/*}
STATE_DIR=/data/adb/geoveil
GUARD_DIR=$STATE_DIR/guard
LOG_FILE=$STATE_DIR/geoveil.log

umask 077
mkdir -p "$GUARD_DIR"

log() {
  printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S' 2>/dev/null || echo unknown-time)" "$*" >> "$LOG_FILE"
}

log "late-start service entered"

# An unfinished hook-install generation means the previous system_server instance
# did not report healthy. Fail open and require explicit user recovery.
if [ -f "$GUARD_DIR/installing" ] && [ ! -f "$GUARD_DIR/healthy" ]; then
  : > "$GUARD_DIR/emergency_disable"
  rm -f "$STATE_DIR/hooks_enabled"
  log "unfinished hook generation detected; emergency pass-through enabled"
fi

# Never activate hooks during early boot. This service is deliberately non-blocking
# to Android startup and only records when the framework reports boot completion.
while [ "$(getprop sys.boot_completed)" != "1" ]; do
  sleep 2
done

: > "$STATE_DIR/boot_ready"
log "boot completed; GeoVeil remains disabled unless valid user state enables it"

exit 0
