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
[[ ! -e module/hooks_enabled ]] || fail "spoofing must not be enabled in the package"

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
  'setprop[[:space:]]+'
  'resetprop[[:space:]]+'
)

for pattern in "${patterns[@]}"; do
  if grep -RInE --exclude='source-guard.sh' -- "$pattern" "${EXISTING_PATHS[@]}"; then
    fail "forbidden source pattern matched: $pattern"
  fi
done

echo "Checking callback scaffold boundaries..."
grep -q 'DLCLOSE_MODULE_LIBRARY' native/src/main/cpp/module.cpp \
  || fail "ordinary app children must unload in the current no-hook scaffold"
grep -q 'postServerSpecialize' native/src/main/cpp/module.cpp \
  || fail "system_server specialization entry point is missing"

echo "GeoVeil source guard passed."
