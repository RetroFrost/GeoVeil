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

if [ -f "$MODPATH/cleanup-legacy.sh" ]; then
  . "$MODPATH/cleanup-legacy.sh"
fi

touch "$MODPATH/skip_mount"
mkdir -p "$MODPATH/logs"

ui_print "- Spoofing default: OFF"
ui_print "- Easy Location Switch default: OFF"
ui_print "- Android settings changes: NONE"
ui_print "- Kernel requirements: NONE beyond working Magisk/Zygisk"
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

ui_print ""
ui_print "========================================"
ui_print " Install complete; reboot before use.   "
ui_print " Hooks remain disabled until configured."
ui_print "========================================"
