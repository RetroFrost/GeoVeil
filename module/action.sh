#!/system/bin/sh

MODDIR=${0%/*}
STATE_DIR=/data/adb/geoveil
LOG_FILE=$STATE_DIR/geoveil.log

mkdir -p "$STATE_DIR"
printf '%s Magisk Action requested\n' "$(date '+%Y-%m-%d %H:%M:%S' 2>/dev/null || echo unknown-time)" >> "$LOG_FILE"

# The parasite-manager bootstrap is intentionally not faked in the safety scaffold.
# Once its shell-host entry point exists, this action will request it without
# force-stopping, killing, or restarting com.android.shell.
echo "GeoVeil manager is not built in this development branch."
echo "No process was restarted and no Android setting was changed."

exit 0
