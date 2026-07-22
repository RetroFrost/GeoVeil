#!/system/bin/sh

MODDIR=${0%/*}
STATE_DIR=/data/adb/geoveil
GUARD_DIR=$STATE_DIR/guard
RUNTIME_DIR=/data/local/tmp/geoveil
LOG_FILE=$STATE_DIR/geoveil.log
BOOT_ID_FILE=/proc/sys/kernel/random/boot_id

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

system_server_pid() {
  pidof system_server 2>/dev/null | awk '{print $1}'
}

mark_emergency() {
  REASON=$1
  : > "$GUARD_DIR/emergency_disable"
  rm -f "$STATE_DIR/hooks_enabled"
  if [ -f "$GUARD_DIR/installing" ]; then
    mv -f "$GUARD_DIR/installing" "$GUARD_DIR/failed" 2>/dev/null || true
  fi
  rm -f "$GUARD_DIR/healthy"

  # The current replacement framework instance must remain pass-through. This
  # marker also prevents the module from loading on the following reboot until
  # the user deliberately clears the fault state.
  : > "$MODDIR/disable"
  log "one-crash fuse activated: $REASON; next boot disabled"
}

current_boot_id() {
  cat "$BOOT_ID_FILE" 2>/dev/null || echo unknown-boot
}

marker_is_well_formed() {
  MARKER_FILE=$1
  set -- $(cat "$MARKER_FILE" 2>/dev/null)
  [ "$#" -eq 3 ] || return 1
  case "$2" in ''|*[!0-9]*) return 1 ;; esac
  case "$3" in ''|*[!0-9]*) return 1 ;; esac
  return 0
}

log "late-start service entered"
stage_manager

BOOT_ID=$(current_boot_id)
MISMATCHES=0
BOOT_RECORDED=0

# This loop is deliberately independent of Android's boot-critical threads. It
# performs only small marker/PID checks every two seconds and never restarts or
# kills system_server, zygote, Shell, or any telephony process.
while true; do
  if [ -f "$GUARD_DIR/installing" ]; then
    if ! marker_is_well_formed "$GUARD_DIR/installing"; then
      mark_emergency "malformed installing marker"
      MISMATCHES=0
    else
      INSTALL_LINE=$(cat "$GUARD_DIR/installing" 2>/dev/null)
      set -- $INSTALL_LINE
      INSTALL_BOOT=$1
      INSTALL_GENERATION=$2
      INSTALL_PID=$3

      if [ "$INSTALL_BOOT" != "$BOOT_ID" ]; then
        mark_emergency "unfinished generation $INSTALL_GENERATION from an earlier boot"
        MISMATCHES=0
      elif [ -f "$GUARD_DIR/healthy" ] && [ "$(cat "$GUARD_DIR/healthy" 2>/dev/null)" = "$INSTALL_LINE" ]; then
        rm -f "$GUARD_DIR/installing" "$GUARD_DIR/healthy" "$GUARD_DIR/observed_system_server.pid"
        MISMATCHES=0
        log "hook generation $INSTALL_GENERATION passed the healthy observation window"
      else
        CURRENT_PID=$(system_server_pid)
        printf '%s\n' "$INSTALL_PID" > "$GUARD_DIR/observed_system_server.pid"
        if [ -z "$CURRENT_PID" ] || [ "$CURRENT_PID" != "$INSTALL_PID" ]; then
          MISMATCHES=$((MISMATCHES + 1))
        else
          MISMATCHES=0
        fi

        # Require three consecutive mismatches to avoid reacting to a transient
        # pidof read while still catching a replacement framework process quickly.
        if [ "$MISMATCHES" -ge 3 ]; then
          mark_emergency "system_server changed during generation $INSTALL_GENERATION"
          MISMATCHES=0
        fi
      fi
    fi
  else
    MISMATCHES=0
  fi

  if [ "$BOOT_RECORDED" -eq 0 ] && [ "$(getprop sys.boot_completed)" = "1" ]; then
    : > "$STATE_DIR/boot_ready"
    BOOT_RECORDED=1
    log "boot completed; GeoVeil remains pass-through unless a validated engine enables it"
  fi

  sleep 2
done
