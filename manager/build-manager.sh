#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ANDROID_PLATFORM="${ANDROID_PLATFORM:-android-36}"
BUILD_TOOLS_VERSION="${BUILD_TOOLS_VERSION:-36.0.0}"
ANDROID_HOME="${ANDROID_HOME:?ANDROID_HOME must point to the Android SDK}"
ANDROID_JAR="$ANDROID_HOME/platforms/$ANDROID_PLATFORM/android.jar"
D8="$ANDROID_HOME/build-tools/$BUILD_TOOLS_VERSION/d8"

[[ -f "$ANDROID_JAR" ]] || {
  echo "Missing Android platform: $ANDROID_JAR" >&2
  exit 1
}
[[ -x "$D8" ]] || {
  echo "Missing D8: $D8" >&2
  exit 1
}

rm -rf "$ROOT/build"
mkdir -p "$ROOT/build/classes" "$ROOT/build/dex"
find "$ROOT/src/main/java" -name '*.java' -print | sort > "$ROOT/build/sources.list"
[[ -s "$ROOT/build/sources.list" ]] || {
  echo "No manager Java sources found" >&2
  exit 1
}

# Use the JDK's Java 8 standard-library signatures and the API 36 android.jar as
# the Android class path. Replacing the entire boot class path with android.jar
# hides LambdaMetafactory from modern javac and prevents lambda compilation.
javac \
  -encoding UTF-8 \
  --release 8 \
  -classpath "$ANDROID_JAR" \
  -d "$ROOT/build/classes" \
  @"$ROOT/build/sources.list"

jar --create --file "$ROOT/build/manager-classes.jar" -C "$ROOT/build/classes" .
"$D8" \
  --lib "$ANDROID_JAR" \
  --min-api 36 \
  --output "$ROOT/build/dex" \
  "$ROOT/build/manager-classes.jar"

(
  cd "$ROOT/build/dex"
  zip -9 -q "$ROOT/build/manager.apk" classes.dex
)

unzip -t "$ROOT/build/manager.apk"
unzip -l "$ROOT/build/manager.apk" | tee "$ROOT/build/manager-contents.txt"
grep -q 'classes.dex' "$ROOT/build/manager-contents.txt"
sha256sum "$ROOT/build/manager.apk" > "$ROOT/build/manager.apk.sha256"

echo "Built $ROOT/build/manager.apk"
