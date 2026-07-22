#!/system/bin/sh

MODDIR=${0%/*}
STATE_DIR=/data/adb/geoveil
RUNTIME_DIR=/data/local/tmp/geoveil
LOG_FILE=$STATE_DIR/geoveil.log
MANAGER_SOURCE=$MODDIR/manager-ui.apk
MANAGER_RUNTIME=$RUNTIME_DIR/manager.apk
READY_MARKER=$RUNTIME_DIR/manager.ready
LAUNCH_CATEGORY=dev.retrofrost.geoveil.LAUNCH_MANAGER

mkdir -p "$STATE_DIR" "$RUNTIME_DIR"
printf '%s Magisk Action requested\n' "$(date '+%Y-%m-%d %H:%M:%S' 2>/dev/null || echo unknown-time)" >> "$LOG_FILE"

if [ ! -s "$MANAGER_SOURCE" ]; then
  echo "GeoVeil manager UI payload is missing from this build."
  echo "The module remains in pass-through mode."
  exit 1
fi

# The Shell child reads the copied APK archive. PackageManager never installs it;
# manager.apk in the module root is reserved for raw DEX consumed by system_server.
cp -f "$MANAGER_SOURCE" "$MANAGER_RUNTIME" || {
  echo "Could not stage the GeoVeil manager UI payload."
  exit 1
}
chown 2000:2000 "$RUNTIME_DIR" "$MANAGER_RUNTIME" >/dev/null 2>&1 || true
chmod 0755 "$RUNTIME_DIR"
chmod 0644 "$MANAGER_RUNTIME"
rm -f "$READY_MARKER"

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
    -f 0x10000000 \
    -n "$COMPONENT" 2>&1
}

STOP_OUTPUT=$(/system/bin/am force-stop --user "$USER_ID" com.android.shell 2>&1)
STOP_STATUS=$?
if [ "$STOP_STATUS" -ne 0 ] || echo "$STOP_OUTPUT" | grep -qiE 'error|exception'; then
  printf '%s Shell host restart failed: %s\n' \
    "$(date '+%Y-%m-%d %H:%M:%S' 2>/dev/null || echo unknown-time)" \
    "$STOP_OUTPUT" >> "$LOG_FILE"
  echo "$STOP_OUTPUT"
  echo "GeoVeil could not restart its Shell UI host."
  echo "The location engine remains in pass-through mode."
  exit 1
fi

# A fresh com.android.shell process is required so Zygisk receives a new
# specialization event and can load GeoVeil before the host activity is used.
sleep 1
OUTPUT=$(launch_manager com.android.shell/.BugreportWarningActivity)
STATUS=$?

printf '%s Manager launch result: %s\n' \
  "$(date '+%Y-%m-%d %H:%M:%S' 2>/dev/null || echo unknown-time)" \
  "$OUTPUT" >> "$LOG_FILE"

echo "$OUTPUT"
if [ "$STATUS" -ne 0 ] || echo "$OUTPUT" | grep -qiE 'error|exception|does not exist'; then
  echo "GeoVeil could not open the Shell host activity on this ROM."
  echo "The location engine remains in pass-through mode."
  exit 1
fi

ATTEMPT=0
while [ "$ATTEMPT" -lt 6 ] && [ ! -s "$READY_MARKER" ]; do
  sleep 1
  ATTEMPT=$((ATTEMPT + 1))
done

if [ ! -s "$READY_MARKER" ]; then
  printf '%s Manager attach timed out after Shell activity launch\n' \
    "$(date '+%Y-%m-%d %H:%M:%S' 2>/dev/null || echo unknown-time)" >> "$LOG_FILE"
  echo "The Shell activity opened, but GeoVeil did not attach within 6 seconds."
  echo "The stock bug-report dialog may still be visible."
  echo "The location engine remains in pass-through mode."
  exit 1
fi

echo "GeoVeil manager attached inside com.android.shell."
echo "The Shell UI host was restarted so Zygisk could inject the manager."
echo "No package was installed; system_server and zygote were not restarted."
exit 0
