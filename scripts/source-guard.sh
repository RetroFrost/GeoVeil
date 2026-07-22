#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

fail() {
  echo "GeoVeil source guard: $*" >&2
  exit 1
}

echo "Checking non-invasive Magisk layout..."
[[ -f module/skip_mount ]] || fail "module/skip_mount is required"
[[ ! -e module/system ]] || fail "system replacement tree is forbidden"
[[ ! -e module/vendor ]] || fail "vendor replacement tree is forbidden"
[[ ! -e module/product ]] || fail "product replacement tree is forbidden"
[[ ! -e module/system_ext ]] || fail "system_ext replacement tree is forbidden"
[[ ! -e module/system.prop ]] || fail "system.prop is forbidden"
[[ ! -e module/sepolicy.rule ]] || fail "unreviewed sepolicy.rule is forbidden"
[[ ! -e module/post-fs-data.sh ]] || fail "early-boot post-fs-data.sh is forbidden"
[[ ! -e module/hooks_enabled ]] || fail "virtualization must not be enabled in the package"
[[ ! -e module/manager.apk ]] || fail "compiled manager.apk must be produced by CI, not committed as a prebuilt"

echo "Checking RC2 manager source contract..."
[[ -f manager/build-manager.sh ]] || fail "manager/build-manager.sh is required"
[[ -f manager/src/main/java/dev/retrofrost/geoveil/manager/GeoVeilEntry.java ]] \
  || fail "manager lifecycle entry point is missing"
[[ -f manager/src/main/java/dev/retrofrost/geoveil/manager/ManagerScreen.java ]] \
  || fail "manager screen implementation is missing"
[[ -f manager/src/main/java/dev/retrofrost/geoveil/manager/BridgeClient.java ]] \
  || fail "bounded manager bridge client is missing"
grep -q 'dev.retrofrost.geoveil.LAUNCH_MANAGER' module/action.sh \
  || fail "Magisk Action does not carry the GeoVeil launch category"
grep -q 'com.android.shell/.BugreportWarningActivity' module/action.sh \
  || fail "Shell trampoline component is missing"
grep -q 'return 0 2>/dev/null || exit 0' module/cleanup-legacy.sh \
  || fail "sourced legacy cleanup must return to the installer"

echo "Scanning executable source for forbidden mechanisms..."
SCAN_PATHS=(native module manager)
EXISTING_PATHS=()
for path in "${SCAN_PATHS[@]}"; do
  [[ -e "$path" ]] && EXISTING_PATHS+=("$path")
done

patterns=(
  'add-test-provider'
  'set-test-provider-location'
  'mockProvider[[:space:]]*=[[:space:]]*true'
  'setMock\([[:space:]]*true'
  'Settings\.Secure'
  'TelephonyManager'
  'getImei\('
  'getMeid\('
  'getDeviceId\('
  '/efs([/"[:space:]]|$)'
  '/persist([/"[:space:]]|$)'
  '/dev/block([/"[:space:]]|$)'
  'force-stop[[:space:]]+com\.android\.shell'
  'kill(all)?[[:space:]]+system_server'
  'kill(all)?[[:space:]]+zygote'
  'setprop[[:space:]]+'
  'resetprop[[:space:]]+'
  'android\.permission\.SYSTEM_ALERT_WINDOW'
  'android\.permission\.REQUEST_INSTALL_PACKAGES'
  'android\.permission\.INTERNET'
)

for pattern in "${patterns[@]}"; do
  if grep -RInE --exclude='source-guard.sh' -- "$pattern" "${EXISTING_PATHS[@]}"; then
    fail "forbidden source pattern matched: $pattern"
  fi
done

echo "Checking specialization boundaries..."
grep -q 'DLCLOSE_MODULE_LIBRARY' native/src/main/cpp/module.cpp \
  || fail "ordinary app children must unload"
grep -q 'kAndroidShellUid = 2000' native/src/main/cpp/module.cpp \
  || fail "Shell child routing must use the dedicated Android shell UID"
grep -q 'postAppSpecialize' native/src/main/cpp/module.cpp \
  || fail "post-specialization manager bootstrap entry point is missing"
grep -q 'postServerSpecialize' native/src/main/cpp/module.cpp \
  || fail "system_server specialization entry point is missing"
grep -q '/data/local/tmp/geoveil/manager.apk' native/src/main/cpp/module.cpp \
  || fail "native Shell bootstrap does not use the staged manager archive"

echo "GeoVeil source guard passed."
