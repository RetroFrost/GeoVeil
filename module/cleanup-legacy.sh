#!/system/bin/sh

# Removes state and processes left by the withdrawn Alpha 1/Alpha 3 builds.
# This file is sourced by customize.sh, so it must return instead of terminating
# the parent Magisk installer. It never restarts system_server, zygote, or Shell.

LEGACY_PERSIST=/data/adb/geoveil
LEGACY_IPC=/data/local/tmp/geoveil
INSTALLED_MODULE=/data/adb/modules/geoveil
LEGACY=0

[ -f "$LEGACY_PERSIST/geoveild.pid" ] && LEGACY=1
[ -d "$LEGACY_IPC/state" ] && LEGACY=1
[ -x "$INSTALLED_MODULE/bin/geoveild" ] && LEGACY=1
if [ -f "$INSTALLED_MODULE/module.prop" ] && grep -qi 'alpha' "$INSTALLED_MODULE/module.prop"; then
  LEGACY=1
fi

if [ "$LEGACY" = 1 ]; then
  ui_print "- Withdrawn GeoVeil alpha detected; cleaning legacy state"

  if [ -f "$LEGACY_PERSIST/geoveild.pid" ]; then
    PID=$(cat "$LEGACY_PERSIST/geoveild.pid" 2>/dev/null)
    if [ -n "$PID" ] && [ -r "/proc/$PID/cmdline" ] && tr '\000' ' ' < "/proc/$PID/cmdline" | grep -q 'geoveild'; then
      kill "$PID" >/dev/null 2>&1 || true
      ui_print "  Stopped legacy geoveild process"
    fi
  fi

  # These commands remove only the withdrawn Alpha 3 test-provider backend and
  # are allowed to fail when that backend is absent on the current device.
  /system/bin/cmd location providers set-test-provider-enabled gps false >/dev/null 2>&1 || true
  /system/bin/cmd location providers remove-test-provider gps >/dev/null 2>&1 || true

  rm -rf "$LEGACY_IPC"
  rm -rf "$LEGACY_PERSIST"

  ui_print "  Removed legacy provider state, PID files, logs, and IPC files"
  ui_print "  com.android.shell and system_server were not restarted"
fi

# Work when sourced by customize.sh and when executed manually during recovery.
return 0 2>/dev/null || exit 0
