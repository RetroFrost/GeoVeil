#!/system/bin/sh

MODDIR=${0%/*}
STATE_DIR=/data/adb/geoveil
GUARD_DIR=$STATE_DIR/guard
RUNTIME_DIR=/data/local/tmp/geoveil
LOG_FILE=$STATE_DIR/geoveil.log
MANAGER_UI=$MODDIR/manager-ui.apk

umask 077
mkdir -p "$GUARD_DIR"

log() {
  printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S' 2>/dev/null || echo unknown-time)" "$*" >> "$LOG_FILE"
}

stage_manager() {
  if [ ! -s "$MANAGER_UI" ]; then
    log "manager UI payload absent; Shell and overlay bootstrap remain inactive"
    return 0
  fi

  mkdir -p "$RUNTIME_DIR" || return 0
  cp -f "$MANAGER_UI" "$RUNTIME_DIR/manager.apk" || {
    log "manager UI payload staging failed"
    return 0
  }
  chown 2000:2000 "$RUNTIME_DIR" "$RUNTIME_DIR/manager.apk" >/dev/null 2>&1 || true
  chmod 0755 "$RUNTIME_DIR"
  chmod 0644 "$RUNTIME_DIR/manager.apk"
  log "top-app overlay runtime staged for specialized foreground processes"
}

enter_emergency() {
  REASON=$1
  : > "$GUARD_DIR/emergency_disable"
  : > "$MODDIR/disable"
  rm -f "$STATE_DIR/hooks_enabled"
  log "$REASON; emergency pass-through enabled and module disabled for next reboot"
}

system_server_pid() {
  pidof system_server 2>/dev/null | awk '{print $1}'
}

monitor_install_generation() {
  # This watcher never kills or restarts a process. It only observes the PID that
  # the companion wrote before hook commit. One unexpected framework replacement
  # blows the fuse so the next system_server stays pass-through.
  while true; do
    [ -f "$GUARD_DIR/emergency_disable" ] && return 0

    if [ -f "$GUARD_DIR/installing" ] && [ ! -f "$GUARD_DIR/healthy" ]; then
      RECORDED_PID=$(awk 'NR==1 {print $2}' "$GUARD_DIR/installing" 2>/dev/null)
      CURRENT_PID=$(system_server_pid)
      case "$RECORDED_PID" in
        ''|*[!0-9]*)
          enter_emergency "invalid hook-install marker"
          return 0
          ;;
      esac
      if [ -z "$CURRENT_PID" ] || [ "$CURRENT_PID" != "$RECORDED_PID" ]; then
        enter_emergency "system_server changed during the hook health window"
        return 0
      fi
    fi
    sleep 1
  done
}

log "late-start service entered"
stage_manager

# A marker surviving into late start means a previous system_server did not
# complete its health observation. Do not attempt another hook commit this boot.
if [ -f "$GUARD_DIR/installing" ] && [ ! -f "$GUARD_DIR/healthy" ]; then
  RECORDED_PID=$(awk 'NR==1 {print $2}' "$GUARD_DIR/installing" 2>/dev/null)
  CURRENT_PID=$(system_server_pid)
  if [ -z "$RECORDED_PID" ] || [ "$CURRENT_PID" != "$RECORDED_PID" ]; then
    enter_emergency "unfinished hook generation detected at late start"
  fi
fi

monitor_install_generation &
MONITOR_PID=$!
printf '%s\n' "$MONITOR_PID" > "$GUARD_DIR/monitor.pid"

# The service does not gate Android startup. It only records boot completion for
# diagnostics while the independent one-crash watcher remains alive.
while [ "$(getprop sys.boot_completed)" != "1" ]; do
  sleep 2
done

: > "$STATE_DIR/boot_ready"
log "boot completed; GeoVeil remains fail-open and the one-crash fuse is armed"

exit 0
