#!/system/bin/sh

SKIPUNZIP=0

ui_print "========================================"
ui_print "              GeoVeil RC2               "
ui_print " Experimental full-engine development  "
ui_print "========================================"
ui_print ""
ui_print "- Architecture: $ARCH"
ui_print "- Android API:  $API"
ui_print "- Magisk:       ${MAGISK_VER:-unknown}"
ui_print "- Zygisk:       ${ZYGISK_ENABLED:-0}"
ui_print ""

[ "$ARCH" = "arm64" ] || abort "! GeoVeil RC2 currently supports arm64 only"
[ "$API" -eq 36 ] || abort "! GeoVeil RC2 currently targets Android 16 / API 36 only"
[ "${ZYGISK_ENABLED:-0}" = "1" ] || abort "! Enable Zygisk in Magisk before installing GeoVeil"

BIN="$MODPATH/zygisk/arm64-v8a.so"
ENGINE_DEX="$MODPATH/manager.apk"
MANAGER_UI="$MODPATH/manager-ui.apk"
[ -s "$BIN" ] || abort "! Missing compiled Zygisk payload; this source tree is not a flashable build"
[ -s "$ENGINE_DEX" ] || abort "! Missing raw engine DEX payload"
[ -s "$MANAGER_UI" ] || abort "! Missing top-app overlay runtime archive"

DEX_MAGIC=$(head -c 3 "$ENGINE_DEX" 2>/dev/null)
[ "$DEX_MAGIC" = "dex" ] || abort "! Engine payload is not a raw DEX file"
unzip -t "$MANAGER_UI" >/dev/null 2>&1 || abort "! Manager UI archive is invalid"

ui_print "- Verifying non-invasive module layout"
[ -e "$MODPATH/system" ] && abort "! Refusing install: system replacement tree detected"
[ -e "$MODPATH/vendor" ] && abort "! Refusing install: vendor replacement tree detected"
[ -e "$MODPATH/product" ] && abort "! Refusing install: product replacement tree detected"
[ -e "$MODPATH/system_ext" ] && abort "! Refusing install: system_ext replacement tree detected"
[ -e "$MODPATH/system.prop" ] && abort "! Refusing install: system.prop is forbidden"
[ -e "$MODPATH/sepolicy.rule" ] && abort "! Refusing install: unreviewed sepolicy.rule detected"
[ -e "$MODPATH/post-fs-data.sh" ] && abort "! Refusing install: early-boot script is forbidden"

if [ -f "$MODPATH/cleanup-legacy.sh" ]; then
  . "$MODPATH/cleanup-legacy.sh"
fi

touch "$MODPATH/skip_mount"
mkdir -p "$MODPATH/logs"

ui_print "- Virtualization default: OFF"
ui_print "- Easy Location Switch default: OFF"
ui_print "- Manager package: dev.retrofrost.geoveil.manager"
ui_print "- Install the matching standalone manager APK separately"
ui_print "- Android settings changes: NONE"
ui_print "- Watchdog / Rescue Party changes: NONE"
ui_print "- Telephony / IMEI / EFS access: NONE"
ui_print ""
ui_print "- Installing permissions"
set_perm_recursive "$MODPATH" 0 0 0755 0644
set_perm "$MODPATH/customize.sh" 0 0 0755
set_perm "$MODPATH/cleanup-legacy.sh" 0 0 0755
set_perm "$MODPATH/service.sh" 0 0 0755
set_perm "$MODPATH/action.sh" 0 0 0755
[ -f "$MODPATH/uninstall.sh" ] && set_perm "$MODPATH/uninstall.sh" 0 0 0755
set_perm "$BIN" 0 0 0644
set_perm "$ENGINE_DEX" 0 0 0644
set_perm "$MANAGER_UI" 0 0 0644

ui_print ""
ui_print "========================================"
ui_print " Install complete; reboot before use.   "
ui_print " Install APK, then use Action or launcher."
ui_print " RC2 requires target-device validation. "
ui_print "========================================"
