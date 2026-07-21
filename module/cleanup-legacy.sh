#!/system/bin/sh

# Removes state and processes left by the withdrawn Alpha 1/Alpha 3 builds.
# This script never restarts system_server, zygote, or com.android.shell.

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

[ "$LEGACY" = 1 ] || exit 0

ui_print "- Withdrawn GeoVeil alpha detected; cleaning legacy state"

if [ -f "$LEGACY_PERSIST/geoveild.pid" ]; then
  PID=$(cat "$LEGACY_PERSIST/geoveild.pid" 2>/dev/null)
  if [ -n "$PID" ] && [ -r "/proc/$PID/cmdline" ] && tr '\000' ' ' < "/proc/$PID/cmdline" | grep -q 'geoveild'; then
    kill "$PID" >/dev/null 2>&1 || true
    ui_print "  Stopped legacy geoveild process"
  fi
fi

# Alpha 3 used a temporary provider named gps. These commands only remove that
# withdrawn backend and are allowed to fail when it is not present.
/system/bin/cmd location providers set-test-provider-enabled gps false >/dev/null 2>&1 || true
/system/bin/cmd location providers remove-test-provider gps >/dev/null 2>&1 || true

rm -rf "$LEGACY_IPC"
rm -rf "$LEGACY_PERSIST"

ui_print "  Removed legacy test-provider state, PID files, logs, and IPC files"
ui_print "  com.android.shell and system_server were not restarted"
exit 0
