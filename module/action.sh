#!/system/bin/sh

STATE_DIR=/data/adb/geoveil
LOG_FILE=$STATE_DIR/geoveil.log
MANAGER_PACKAGE=dev.retrofrost.geoveil.manager
MANAGER_COMPONENT=$MANAGER_PACKAGE/.MainActivity

mkdir -p "$STATE_DIR"
printf '%s Magisk Action requested standalone manager\n' \
  "$(date '+%Y-%m-%d %H:%M:%S' 2>/dev/null || echo unknown-time)" >> "$LOG_FILE"

USER_ID=$(/system/bin/am get-current-user 2>/dev/null | tail -n 1)
case "$USER_ID" in
  ''|*[!0-9]*) USER_ID=0 ;;
esac

if ! /system/bin/pm path --user "$USER_ID" "$MANAGER_PACKAGE" >/dev/null 2>&1; then
  echo "GeoVeil Manager is not installed for Android user $USER_ID."
  echo "Install the matching standalone GeoVeil Manager APK, then retry Action."
  echo "The location engine remains in pass-through mode."
  exit 1
fi

OUTPUT=$(/system/bin/am start \
  --user "$USER_ID" \
  -a android.intent.action.MAIN \
  -c android.intent.category.LAUNCHER \
  -f 0x10000000 \
  -n "$MANAGER_COMPONENT" 2>&1)
STATUS=$?

printf '%s Standalone manager launch result: %s\n' \
  "$(date '+%Y-%m-%d %H:%M:%S' 2>/dev/null || echo unknown-time)" \
  "$OUTPUT" >> "$LOG_FILE"
echo "$OUTPUT"

if [ "$STATUS" -ne 0 ] || echo "$OUTPUT" | grep -qiE 'error|exception|does not exist'; then
  echo "GeoVeil could not launch the installed manager application."
  echo "No framework process was restarted; the engine remains pass-through."
  exit 1
fi

echo "GeoVeil Manager launch requested."
echo "No Shell, system_server, or zygote process was stopped or restarted."
exit 0
