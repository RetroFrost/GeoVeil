#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
fail() { echo "GeoVeil source guard: $*" >&2; exit 1; }
require_file() { [[ -f "$1" ]] || fail "required source is missing: $1"; }
require_text() { grep -Fq -- "$1" "$2" || fail "$3"; }

echo "Checking LSPosed module contract..."
for source in \
  manager/build-manager.sh \
  manager/src/main/AndroidManifest.xml \
  manager/src/main/java/dev/retrofrost/geoveil/manager/GeoVeilApplication.java \
  manager/src/main/java/dev/retrofrost/geoveil/manager/RemoteState.java \
  manager/src/main/java/dev/retrofrost/geoveil/manager/BridgeClient.java \
  manager/src/main/java/dev/retrofrost/geoveil/xposed/GeoVeilModule.java \
  manager/src/main/java/dev/retrofrost/geoveil/xposed/JoystickOverlay.java \
  manager/src/main/resources/META-INF/xposed/java_init.list; do
  require_file "$source"
done
require_text 'dev.retrofrost.geoveil.xposed.GeoVeilModule' manager/src/main/resources/META-INF/xposed/java_init.list "missing LSPosed entry point"
require_text 'XposedServiceHelper.registerListener' manager/src/main/java/dev/retrofrost/geoveil/manager/GeoVeilApplication.java "manager does not bind LSPosed service"
require_text 'getRemotePreferences' manager/src/main/java/dev/retrofrost/geoveil/xposed/GeoVeilModule.java "module does not read live shared settings"
require_text 'getLatitude' manager/src/main/java/dev/retrofrost/geoveil/xposed/GeoVeilModule.java "latitude hook missing"
require_text 'getLongitude' manager/src/main/java/dev/retrofrost/geoveil/xposed/GeoVeilModule.java "longitude hook missing"
require_text 'getLastKnownLocation' manager/src/main/java/dev/retrofrost/geoveil/xposed/GeoVeilModule.java "LocationManager hook missing"
require_text 'GeoVeil-LSPosed.apk' manager/build-manager.sh "build does not produce LSPosed APK"
require_text 'libxposed-service' manager/build-manager.sh "LSPosed service runtime is not packaged"
require_text 'META-INF/xposed/java_init.list' manager/build-manager.sh "LSPosed metadata is not packaged"
require_text 'android.intent.category.LAUNCHER' manager/src/main/AndroidManifest.xml "manager launcher missing"
require_text 'android:exported="true"' manager/src/main/AndroidManifest.xml "manager launcher not exported"

echo "Scanning executable source for forbidden mechanisms..."
SCAN_PATHS=(manager)
patterns=(
  'add-test-provider' 'set-test-provider-location' 'mockProvider[[:space:]]*=[[:space:]]*true'
  'setMock\([[:space:]]*true' 'Settings\.Secure' 'TelephonyManager' 'getImei\('
  'getMeid\(' 'getDeviceId\(' '/efs([/"[:space:]]|$)' '/persist([/"[:space:]]|$)'
  '/dev/block([/"[:space:]]|$)' 'force-stop[[:space:]]+com\.android\.shell'
  'kill(all)?[[:space:]]+system_server' 'kill(all)?[[:space:]]+zygote'
  'setprop[[:space:]]+' 'resetprop[[:space:]]+' 'android\.permission\.SYSTEM_ALERT_WINDOW'
  'android\.permission\.REQUEST_INSTALL_PACKAGES' 'android\.permission\.INTERNET'
)
for pattern in "${patterns[@]}"; do
  if grep -RInE --exclude='source-guard.sh' -- "$pattern" "${SCAN_PATHS[@]}"; then
    fail "forbidden source pattern matched: $pattern"
  fi
done
echo "GeoVeil LSPosed source guard passed."
