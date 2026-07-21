#!/system/bin/sh

SKIPUNZIP=0

ui_print "========================================"
ui_print "              GeoVeil RC1               "
ui_print "        Zygisk safety-core installer    "
ui_print "========================================"
ui_print ""
ui_print "- Architecture: $ARCH"
ui_print "- Android API:  $API"
ui_print "- Magisk:       ${MAGISK_VER:-unknown}"
ui_print "- Zygisk:       ${ZYGISK_ENABLED:-0}"
ui_print ""

[ "$ARCH" = "arm64" ] || abort "! GeoVeil RC1 currently supports arm64 only"
[ "$API" -ge 35 ] || abort "! Android API 35 or newer is required"
[ "${ZYGISK_ENABLED:-0}" = "1" ] || abort "! Enable Zygisk in Magisk before installing GeoVeil"

BIN="$MODPATH/zygisk/arm64-v8a.so"
[ -s "$BIN" ] || abort "! Missing compiled Zygisk payload; this source tree is not a flashable release"

ui_print "- Verifying non-invasive module layout"
[ -e "$MODPATH/system" ] && abort "! Refusing install: system replacement tree detected"
[ -e "$MODPATH/vendor" ] && abort "! Refusing install: vendor replacement tree detected"
[ -e "$MODPATH/system.prop" ] && abort "! Refusing install: system.prop is forbidden"
[ -e "$MODPATH/sepolicy.rule" ] && abort "! Refusing install: unreviewed sepolicy.rule detected"
[ -e "$MODPATH/post-fs-data.sh" ] && abort "! Refusing install: early-boot script is forbidden"

ui_print ""
ui_print "- Cleaning previous GeoVeil installs"
OLD_MOD=/data/adb/modules/geoveil
OLD_CTL="$OLD_MOD/bin/geoveilctl"
OLD_STATE=/data/adb/geoveil
OLD_TMP=/data/local/tmp/geoveil

# Alpha builds included a controller capable of restoring the genuine provider.
# Ask it to do so before deleting its runtime state. The RC1 package itself does
# not contain or invoke an Android test-provider backend.
if [ -x "$OLD_CTL" ]; then
  ui_print "  Restoring genuine location through the previous controller"
  "$OLD_CTL" real >/dev/null 2>&1 || ui_print "  Previous controller did not respond; continuing fail-open"
fi

# Stop only a PID that can be verified as the old GeoVeil daemon. Never kill a
# framework process, Zygote, system_server, or com.android.shell.
if [ -f "$OLD_STATE/geoveild.pid" ]; then
  OLD_PID=$(cat "$OLD_STATE/geoveild.pid" 2>/dev/null)
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

# Remove obsolete standalone-manager prototypes if they were ever installed.
# The RC1 manager remains parasitic and is not installed as a launcher package.
for OLD_PACKAGE in com.retrofrost.geoveil com.retrofrost.geoveil.manager; do
  if /system/bin/pm path "$OLD_PACKAGE" >/dev/null 2>&1; then
    ui_print "  Removing obsolete package: $OLD_PACKAGE"
    /system/bin/pm uninstall "$OLD_PACKAGE" >/dev/null 2>&1 || true
  fi
done

rm -rf "$OLD_STATE" "$OLD_TMP"
ui_print "  Previous runtime state removed"

touch "$MODPATH/skip_mount"
mkdir -p "$MODPATH/logs" /data/adb/geoveil/guard
rm -f /data/adb/geoveil/hooks_enabled /data/adb/geoveil/guard/installing
: > /data/adb/geoveil/guard/emergency_disable

ui_print ""
ui_print "- Spoofing default: OFF"
ui_print "- Easy Location Switch default: OFF"
ui_print "- Android settings changes: NONE"
ui_print "- Kernel requirements: NONE beyond working Magisk/Zygisk"
ui_print "- Telephony / IMEI / EFS access: NONE"
ui_print "- Android Watchdog modification: NONE"
ui_print ""
ui_print "- Installing permissions"
set_perm_recursive "$MODPATH" 0 0 0755 0644
set_perm "$MODPATH/customize.sh" 0 0 0755
set_perm "$MODPATH/service.sh" 0 0 0755
set_perm "$MODPATH/action.sh" 0 0 0755
set_perm "$MODPATH/uninstall.sh" 0 0 0755
set_perm "$BIN" 0 0 0644
set_perm_recursive /data/adb/geoveil 0 0 0700 0600

ui_print ""
ui_print "========================================"
ui_print " Install complete; reboot before use.   "
ui_print " Hooks remain disabled until configured."
ui_print "========================================"