#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

fail() {
  echo "GeoVeil source guard: $*" >&2
  exit 1
}

require_file() {
  [[ -f "$1" ]] || fail "required source is missing: $1"
}

require_text() {
  local pattern=$1
  local path=$2
  local message=$3
  grep -Fq -- "$pattern" "$path" || fail "$message"
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
[[ ! -e module/manager.apk ]] || fail "raw manager DEX must be produced by CI, not committed"
[[ ! -e module/manager-ui.apk ]] || fail "Shell manager archive must be produced by CI, not committed"

for script in module/customize.sh module/cleanup-legacy.sh module/service.sh module/action.sh; do
  require_file "$script"
  sh -n "$script" || fail "shell syntax check failed: $script"
done

echo "Checking complete RC2 Java source contract..."
for source in \
  manager/build-manager.sh \
  manager/src/main/java/dev/retrofrost/geoveil/engine/DeliveryHook.java \
  manager/src/main/java/dev/retrofrost/geoveil/manager/GeoVeilEntry.java \
  manager/src/main/java/dev/retrofrost/geoveil/manager/ManagerScreen.java \
  manager/src/main/java/dev/retrofrost/geoveil/manager/NativeBridge.java \
  manager/src/main/java/dev/retrofrost/geoveil/manager/BridgeClient.java \
  manager/src/main/java/dev/retrofrost/geoveil/manager/EasyLocationController.java \
  manager/src/main/java/dev/retrofrost/geoveil/manager/MovementPanel.java \
  manager/src/main/java/dev/retrofrost/geoveil/manager/JoystickView.java \
  manager/src/main/java/dev/retrofrost/geoveil/manager/OverlayEntry.java; do
  require_file "$source"
done

require_text 'dev.retrofrost.geoveil.LAUNCH_MANAGER' module/action.sh \
  "Magisk Action does not carry the GeoVeil launch category"
require_text 'com.android.shell/.BugreportWarningActivity' module/action.sh \
  "Shell trampoline component is missing"
require_text '-f 0x10000000' module/action.sh \
  "Magisk Action must pass FLAG_ACTIVITY_NEW_TASK using Android 16 intent syntax"
require_text '/system/bin/am force-stop --user "$USER_ID" com.android.shell' module/action.sh \
  "parasitic manager launch must restart only its Shell UI host"
require_text 'READY_MARKER=$RUNTIME_DIR/manager.ready' module/action.sh \
  "Magisk Action must verify that GeoVeil replaced the Shell activity"
require_text 'new FileOutputStream(READY_MARKER, false)' \
  manager/src/main/java/dev/retrofrost/geoveil/manager/GeoVeilEntry.java \
  "manager does not publish its verified attach marker"
if grep -Fq -- '--activity-new-task' module/action.sh; then
  fail "unsupported am start option --activity-new-task is forbidden"
fi
if grep -Fq -- 'com.android.shell/.BugreportActivity' module/action.sh; then
  fail "nonexistent Android 16 Shell fallback activity is forbidden"
fi
require_text 'MANAGER_SOURCE=$MODDIR/manager-ui.apk' module/action.sh \
  "Magisk Action must stage the Shell manager archive, not the raw engine DEX"
require_text 'MANAGER_UI=$MODDIR/manager-ui.apk' module/service.sh \
  "late-start service must stage the Shell manager archive separately"
require_text 'return 0 2>/dev/null || exit 0' module/cleanup-legacy.sh \
  "sourced legacy cleanup must return to the installer"

echo "Checking native engine, companion, and hook contract..."
for source in \
  native/src/main/cpp/module.cpp \
  native/src/main/cpp/bridge.cpp \
  native/src/main/cpp/bridge.hpp \
  native/src/main/cpp/companion.cpp \
  native/src/main/cpp/engine.cpp \
  native/src/main/cpp/engine.hpp \
  native/src/main/cpp/ipc.hpp \
  native/src/main/cpp/state.hpp \
  scripts/fetch-hook-deps.sh; do
  require_file "$source"
done

require_text 'GetStaticMethodID(result, "wrap",' native/src/main/cpp/engine.cpp \
  "Android 16 LocationResult.wrap(List) compatibility probe is missing"
if grep -Fq 'GetStaticMethodID(result, "create",' native/src/main/cpp/engine.cpp; then
  fail "obsolete LocationResult.create(List) lookup would leave the engine pass-through"
fi
require_text 'REGISTER_ZYGISK_COMPANION' native/src/main/cpp/companion.cpp \
  "root companion entry is not registered"
require_text 'lsplant_static' native/CMakeLists.txt \
  "LSPlant is not linked into the active engine"
require_text 'dobby_static' native/CMakeLists.txt \
  "Dobby is not linked into the active engine"
require_text '-DANDROID_PLATFORM="${NATIVE_PLATFORM}"' .github/workflows/build.yml \
  "native CI must use the NDK-supported native API level"
require_text 'manager/build/dex/classes.dex out/stage/manager.apk' .github/workflows/build.yml \
  "system_server must receive a raw DEX, not an APK/ZIP container"
require_text 'manager/build/manager.apk out/stage/manager-ui.apk' .github/workflows/build.yml \
  "Shell manager archive is not packaged separately"

echo "Checking one-crash fuse and recovery markers..."
require_text 'GUARD_DIR/emergency_disable' module/service.sh \
  "late-start service cannot activate emergency pass-through"
require_text 'MODDIR/disable' module/service.sh \
  "late-start service cannot disable the module for the following boot"
require_text 'engine_begin' native/src/main/cpp/module.cpp \
  "system_server does not arm the hook-install generation"
require_text 'engine_healthy' native/src/main/cpp/module.cpp \
  "system_server does not report a healthy generation"
require_text 'engine_abort' native/src/main/cpp/module.cpp \
  "failed hook installation does not abort cleanly"

echo "Scanning executable source for forbidden mechanisms..."
SCAN_PATHS=(native module manager)
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
  'kill(all)?[[:space:]]+system_server'
  'kill(all)?[[:space:]]+zygote'
  'setprop[[:space:]]+'
  'resetprop[[:space:]]+'
  'android\.permission\.SYSTEM_ALERT_WINDOW'
  'android\.permission\.REQUEST_INSTALL_PACKAGES'
  'android\.permission\.INTERNET'
)

for pattern in "${patterns[@]}"; do
  if grep -RInE --exclude='source-guard.sh' -- "$pattern" "${SCAN_PATHS[@]}"; then
    fail "forbidden source pattern matched: $pattern"
  fi
done

echo "Checking specialization boundaries..."
require_text 'DLCLOSE_MODULE_LIBRARY' native/src/main/cpp/module.cpp \
  "unrelated application children must unload"
require_text 'kAndroidShellUid = 2000' native/src/main/cpp/module.cpp \
  "Shell routing must use Android's dedicated shell UID"
require_text 'connectCompanion()' native/src/main/cpp/module.cpp \
  "pre-specialization companion connection is missing"
require_text 'postAppSpecialize' native/src/main/cpp/module.cpp \
  "post-specialization manager/overlay bootstrap is missing"
require_text 'postServerSpecialize' native/src/main/cpp/module.cpp \
  "post-specialization system_server engine bootstrap is missing"
require_text '/data/local/tmp/geoveil/manager.apk' native/src/main/cpp/module.cpp \
  "specialized app bootstrap does not use the staged Shell manager archive"

echo "GeoVeil complete RC2 source guard passed."
