#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ANDROID_PLATFORM="${ANDROID_PLATFORM:-android-36}"
BUILD_TOOLS_VERSION="${BUILD_TOOLS_VERSION:-36.0.0}"
ANDROID_HOME="${ANDROID_HOME:?ANDROID_HOME must point to the Android SDK}"
ANDROID_JAR="$ANDROID_HOME/platforms/$ANDROID_PLATFORM/android.jar"
BUILD_TOOLS="$ANDROID_HOME/build-tools/$BUILD_TOOLS_VERSION"
D8="$BUILD_TOOLS/d8"; AAPT2="$BUILD_TOOLS/aapt2"; ZIPALIGN="$BUILD_TOOLS/zipalign"; APKSIGNER="$BUILD_TOOLS/apksigner"
MANIFEST="$ROOT/src/main/AndroidManifest.xml"; RESOURCES="$ROOT/src/main/res"; RAW_RESOURCES="$ROOT/src/main/resources"
VERSION_NAME="0.3.0-lsposed1"; VERSION_CODE=301
LIBXPOSED_VERSION="101.0.0"; MAVEN="https://repo1.maven.org/maven2/io/github/libxposed"

for required in "$ANDROID_JAR" "$D8" "$AAPT2" "$ZIPALIGN" "$APKSIGNER" "$MANIFEST"; do
  [[ -e "$required" ]] || { echo "Missing Android build input: $required" >&2; exit 1; }
done

rm -rf "$ROOT/build"
mkdir -p "$ROOT/build/classes" "$ROOT/build/dex" "$ROOT/build/deps"
curl -fsSL "$MAVEN/api/$LIBXPOSED_VERSION/api-$LIBXPOSED_VERSION.aar" -o "$ROOT/build/deps/api.aar"
curl -fsSL "$MAVEN/service/$LIBXPOSED_VERSION/service-$LIBXPOSED_VERSION.aar" -o "$ROOT/build/deps/service.aar"
unzip -p "$ROOT/build/deps/api.aar" classes.jar > "$ROOT/build/deps/libxposed-api.jar"
unzip -p "$ROOT/build/deps/service.aar" classes.jar > "$ROOT/build/deps/libxposed-service.jar"
test -s "$ROOT/build/deps/libxposed-api.jar" && test -s "$ROOT/build/deps/libxposed-service.jar"

find "$ROOT/src/main/java" -name '*.java' -print | sort > "$ROOT/build/sources.list"
javac -encoding UTF-8 --release 8 \
  -classpath "$ANDROID_JAR:$ROOT/build/deps/libxposed-api.jar:$ROOT/build/deps/libxposed-service.jar" \
  -d "$ROOT/build/classes" @"$ROOT/build/sources.list"
(
  cd "$ROOT/build/classes"
  zip -q -r "$ROOT/build/manager-classes.jar" .
)
"$D8" --lib "$ANDROID_JAR" --classpath "$ROOT/build/deps/libxposed-api.jar" --min-api 31 \
  --output "$ROOT/build/dex" "$ROOT/build/manager-classes.jar" "$ROOT/build/deps/libxposed-service.jar"

"$AAPT2" compile --dir "$RESOURCES" -o "$ROOT/build/resources.zip"
"$AAPT2" link -o "$ROOT/build/unsigned-unaligned.apk" -I "$ANDROID_JAR" --manifest "$MANIFEST" \
  --min-sdk-version 31 --target-sdk-version 36 --version-code "$VERSION_CODE" --version-name "$VERSION_NAME" \
  "$ROOT/build/resources.zip"
(
  cd "$ROOT/build/dex"
  zip -q -0 "$ROOT/build/unsigned-unaligned.apk" classes.dex
)
(
  cd "$RAW_RESOURCES"
  zip -q "$ROOT/build/unsigned-unaligned.apk" META-INF/xposed/java_init.list
)
"$ZIPALIGN" -f -p 4 "$ROOT/build/unsigned-unaligned.apk" "$ROOT/build/unsigned.apk"

SIGNING_DIR="${GEOVEIL_SIGNING_DIR:-$ROOT/.signing}"; KEYSTORE="${GEOVEIL_KEYSTORE:-$SIGNING_DIR/geoveil-development.jks}"; KEY_PASSWORD=geoveil-ci-pair
mkdir -p "$SIGNING_DIR"
if [[ ! -s "$KEYSTORE" ]]; then
  keytool -genkeypair -keystore "$KEYSTORE" -storepass "$KEY_PASSWORD" -keypass "$KEY_PASSWORD" \
    -alias geoveil-manager -keyalg RSA -keysize 3072 -validity 10000 \
    -dname "CN=GeoVeil Development Build,O=RetroFrost" -noprompt >/dev/null 2>&1
fi
"$APKSIGNER" sign --ks "$KEYSTORE" --ks-key-alias geoveil-manager --ks-pass "pass:$KEY_PASSWORD" \
  --key-pass "pass:$KEY_PASSWORD" --out "$ROOT/build/GeoVeil-LSPosed.apk" "$ROOT/build/unsigned.apk"
"$APKSIGNER" verify --verbose --print-certs "$ROOT/build/GeoVeil-LSPosed.apk" | tee "$ROOT/build/certificates.txt"
"$AAPT2" dump badging "$ROOT/build/GeoVeil-LSPosed.apk" | tee "$ROOT/build/badging.txt"
unzip -t "$ROOT/build/GeoVeil-LSPosed.apk"
unzip -l "$ROOT/build/GeoVeil-LSPosed.apk" | tee "$ROOT/build/contents.txt"
grep -q "META-INF/xposed/java_init.list" "$ROOT/build/contents.txt"
grep -q "classes.dex" "$ROOT/build/contents.txt"
grep -q "launchable-activity: name='dev.retrofrost.geoveil.manager.MainActivity'" "$ROOT/build/badging.txt"
sha256sum "$ROOT/build/GeoVeil-LSPosed.apk" > "$ROOT/build/GeoVeil-LSPosed.apk.sha256"
echo "Built $ROOT/build/GeoVeil-LSPosed.apk"
