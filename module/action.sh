#!/system/bin/sh

MODDIR=${0%/*}
STATE_DIR=/data/adb/geoveil
RUNTIME_DIR=/data/local/tmp/geoveil
LOG_FILE=$STATE_DIR/geoveil.log
MANAGER_SOURCE=$MODDIR/manager.apk
MANAGER_RUNTIME=$RUNTIME_DIR/manager.apk
LAUNCH_CATEGORY=dev.retrofrost.geoveil.LAUNCH_MANAGER

mkdir -p "$STATE_DIR" "$RUNTIME_DIR"
printf '%s Magisk Action requested\n' "$(date '+%Y-%m-%d %H:%M:%S' 2>/dev/null || echo unknown-time)" >> "$LOG_FILE"

if [ ! -s "$MANAGER_SOURCE" ]; then
  echo "GeoVeil manager payload is missing from this build."
  echo "The module remains in pass-through mode."
  exit 1
fi

# The shell child reads only this copied manager DEX archive. Nothing is installed
# into PackageManager and no launcher-visible package is created.
cp -f "$MANAGER_SOURCE" "$MANAGER_RUNTIME" || {
  echo "Could not stage the GeoVeil manager payload."
  exit 1
}
chown 2000:2000 "$RUNTIME_DIR" "$MANAGER_RUNTIME" >/dev/null 2>&1 || true
chmod 0755 "$RUNTIME_DIR"
chmod 0644 "$MANAGER_RUNTIME"

USER_ID=$(/system/bin/am get-current-user 2>/dev/null | tail -n 1)
case "$USER_ID" in
  ''|*[!0-9]*) USER_ID=0 ;;
esac

launch_manager() {
  COMPONENT=$1
  /system/bin/am start \
    --user "$USER_ID" \
    -a android.intent.action.MAIN \
    -c "$LAUNCH_CATEGORY" \
    -p com.android.shell \
    -n "$COMPONENT" \
    --activity-new-task 2>&1
}

OUTPUT=$(launch_manager com.android.shell/.BugreportWarningActivity)
STATUS=$?
if [ "$STATUS" -ne 0 ] || echo "$OUTPUT" | grep -qiE 'error|exception|does not exist'; then
  OUTPUT=$(launch_manager com.android.shell/.BugreportActivity)
  STATUS=$?
fi

printf '%s Manager launch result: %s\n' \
  "$(date '+%Y-%m-%d %H:%M:%S' 2>/dev/null || echo unknown-time)" \
  "$OUTPUT" >> "$LOG_FILE"

echo "$OUTPUT"
if [ "$STATUS" -ne 0 ] || echo "$OUTPUT" | grep -qiE 'error|exception|does not exist'; then
  echo "GeoVeil could not open the Shell host activity on this ROM."
  echo "No process was stopped or restarted; the engine remains pass-through."
  exit 1
fi

echo "GeoVeil manager launch requested through com.android.shell."
echo "No package was installed and no process was force-stopped."
exit 0
