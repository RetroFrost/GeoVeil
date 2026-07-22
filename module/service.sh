#!/system/bin/sh

MODDIR=${0%/*}
STATE_DIR=/data/adb/geoveil
GUARD_DIR=$STATE_DIR/guard
RUNTIME_DIR=/data/local/tmp/geoveil
LOG_FILE=$STATE_DIR/geoveil.log

umask 077
mkdir -p "$GUARD_DIR"

log() {
  printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S' 2>/dev/null || echo unknown-time)" "$*" >> "$LOG_FILE"
}

stage_manager() {
  if [ ! -s "$MODDIR/manager.apk" ]; then
    log "manager payload absent; Shell bootstrap remains inactive"
    return 0
  fi

  mkdir -p "$RUNTIME_DIR" || return 0
  cp -f "$MODDIR/manager.apk" "$RUNTIME_DIR/manager.apk" || {
    log "manager payload staging failed"
    return 0
  }
  chown 2000:2000 "$RUNTIME_DIR" "$RUNTIME_DIR/manager.apk" >/dev/null 2>&1 || true
  chmod 0755 "$RUNTIME_DIR"
  chmod 0644 "$RUNTIME_DIR/manager.apk"
  log "manager payload staged for the specialized Shell child"
}

log "late-start service entered"
stage_manager

# An unfinished hook-install generation means the previous system_server instance
# did not report healthy. Fail open and require explicit user recovery.
if [ -f "$GUARD_DIR/installing" ] && [ ! -f "$GUARD_DIR/healthy" ]; then
  : > "$GUARD_DIR/emergency_disable"
  rm -f "$STATE_DIR/hooks_enabled"
  log "unfinished hook generation detected; emergency pass-through enabled"
fi

# Never activate location hooks during boot. The late-start service runs separately
# from Android startup and only records when the framework reports boot completion.
while [ "$(getprop sys.boot_completed)" != "1" ]; do
  sleep 2
done

: > "$STATE_DIR/boot_ready"
log "boot completed; GeoVeil remains pass-through unless a validated bridge enables it"

exit 0
