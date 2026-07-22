#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ANDROID_PLATFORM="${ANDROID_PLATFORM:-android-36}"
BUILD_TOOLS_VERSION="${BUILD_TOOLS_VERSION:-36.0.0}"
ANDROID_HOME="${ANDROID_HOME:?ANDROID_HOME must point to the Android SDK}"
ANDROID_JAR="$ANDROID_HOME/platforms/$ANDROID_PLATFORM/android.jar"
BUILD_TOOLS="$ANDROID_HOME/build-tools/$BUILD_TOOLS_VERSION"
D8="$BUILD_TOOLS/d8"
AAPT2="$BUILD_TOOLS/aapt2"
ZIPALIGN="$BUILD_TOOLS/zipalign"
APKSIGNER="$BUILD_TOOLS/apksigner"
MANIFEST="$ROOT/src/main/AndroidManifest.xml"
RESOURCES="$ROOT/src/main/res"
VERSION_NAME="0.2.0-rc2-dev-standalone4"
VERSION_CODE=206

for required in "$ANDROID_JAR" "$D8" "$AAPT2" "$ZIPALIGN" "$APKSIGNER" "$MANIFEST"; do
  [[ -e "$required" ]] || {
    echo "Missing Android build input: $required" >&2
    exit 1
  }
done

rm -rf "$ROOT/build"
mkdir -p "$ROOT/build/classes" "$ROOT/build/dex"
find "$ROOT/src/main/java" -name '*.java' -print | sort > "$ROOT/build/sources.list"
[[ -s "$ROOT/build/sources.list" ]] || {
  echo "No manager Java sources found" >&2
  exit 1
}

javac \
  -encoding UTF-8 \
  --release 8 \
  -classpath "$ANDROID_JAR" \
  -d "$ROOT/build/classes" \
  @"$ROOT/build/sources.list"

jar --create --file "$ROOT/build/manager-classes.jar" -C "$ROOT/build/classes" .
"$D8" \
  --lib "$ANDROID_JAR" \
  --min-api 31 \
  --output "$ROOT/build/dex" \
  "$ROOT/build/manager-classes.jar"

# Raw archive retained for system_server engine loading and top-app overlay loading.
(
  cd "$ROOT/build/dex"
  zip -9 -q "$ROOT/build/manager.apk" classes.dex
)

"$AAPT2" compile \
  --dir "$RESOURCES" \
  -o "$ROOT/build/resources.zip"
"$AAPT2" link \
  -o "$ROOT/build/standalone-unsigned-unaligned.apk" \
  -I "$ANDROID_JAR" \
  --manifest "$MANIFEST" \
  --min-sdk-version 31 \
  --target-sdk-version 36 \
  --version-code "$VERSION_CODE" \
  --version-name "$VERSION_NAME" \
  "$ROOT/build/resources.zip"
(
  cd "$ROOT/build/dex"
  zip -q -0 "$ROOT/build/standalone-unsigned-unaligned.apk" classes.dex
)
"$ZIPALIGN" -f -p 4 \
  "$ROOT/build/standalone-unsigned-unaligned.apk" \
  "$ROOT/build/standalone-unsigned.apk"

# Development CI caches this non-release key outside the disposable build tree so
# later development APKs remain upgrade-compatible. Release signing must replace it.
SIGNING_DIR="${GEOVEIL_SIGNING_DIR:-$ROOT/.signing}"
KEYSTORE="${GEOVEIL_KEYSTORE:-$SIGNING_DIR/geoveil-development.jks}"
KEY_PASSWORD=geoveil-ci-pair
mkdir -p "$SIGNING_DIR"
if [[ ! -s "$KEYSTORE" ]]; then
  keytool -genkeypair \
    -keystore "$KEYSTORE" \
    -storepass "$KEY_PASSWORD" \
    -keypass "$KEY_PASSWORD" \
    -alias geoveil-manager \
    -keyalg RSA \
    -keysize 3072 \
    -validity 10000 \
    -dname "CN=GeoVeil Development Build,O=RetroFrost" \
    -noprompt >/dev/null 2>&1
fi
"$APKSIGNER" sign \
  --ks "$KEYSTORE" \
  --ks-key-alias geoveil-manager \
  --ks-pass "pass:$KEY_PASSWORD" \
  --key-pass "pass:$KEY_PASSWORD" \
  --out "$ROOT/build/GeoVeil-Manager-standalone.apk" \
  "$ROOT/build/standalone-unsigned.apk"

"$APKSIGNER" verify --verbose --print-certs \
  "$ROOT/build/GeoVeil-Manager-standalone.apk" \
  | tee "$ROOT/build/standalone-certificates.txt"
"$AAPT2" dump badging "$ROOT/build/GeoVeil-Manager-standalone.apk" \
  | tee "$ROOT/build/standalone-badging.txt"
grep -q "package: name='dev.retrofrost.geoveil.manager'" \
  "$ROOT/build/standalone-badging.txt"
grep -q "launchable-activity: name='dev.retrofrost.geoveil.manager.MainActivity'" \
  "$ROOT/build/standalone-badging.txt"

unzip -t "$ROOT/build/manager.apk"
unzip -l "$ROOT/build/manager.apk" | tee "$ROOT/build/manager-contents.txt"
grep -q 'classes.dex' "$ROOT/build/manager-contents.txt"
(
  cd "$ROOT/build"
  sha256sum manager.apk > manager.apk.sha256
  sha256sum GeoVeil-Manager-standalone.apk \
    > GeoVeil-Manager-standalone.apk.sha256
)

echo "Built $ROOT/build/manager.apk"
echo "Built $ROOT/build/GeoVeil-Manager-standalone.apk"
