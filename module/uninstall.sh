#!/system/bin/sh

STATE_DIR=/data/adb/geoveil
TMP_DIR=/data/local/tmp/geoveil

# Disable persisted activation before removing state. Uninstalling GeoVeil must
# never restart or terminate Zygote, system_server, or com.android.shell.
rm -f "$STATE_DIR/hooks_enabled"
: > "$STATE_DIR/guard/emergency_disable" 2>/dev/null || true

# Stop only a verified legacy GeoVeil daemon, if an alpha left one behind.
if [ -f "$STATE_DIR/geoveild.pid" ]; then
  OLD_PID=$(cat "$STATE_DIR/geoveild.pid" 2>/dev/null)
  case "$OLD_PID" in
    ''|*[!0-9]*) ;;
    *)
      OLD_CMD=$(tr '\000' ' ' < "/proc/$OLD_PID/cmdline" 2>/dev/null)
      case "$OLD_CMD" in
        *geoveild*) kill "$OLD_PID" >/dev/null 2>&1 || true ;;
      esac
      ;;
  esac
fi

rm -rf "$STATE_DIR" "$TMP_DIR"
exit 0
