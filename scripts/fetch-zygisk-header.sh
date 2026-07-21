#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="$ROOT/native/third_party/zygisk/zygisk.hpp"
PINNED_COMMIT="26ae876a437f4c34c5d1ab21d6aeac736301d2d0"
URL="https://raw.githubusercontent.com/topjohnwu/zygisk-module-sample/${PINNED_COMMIT}/module/jni/zygisk.hpp"
EXPECTED_SHA256=""

mkdir -p "$(dirname "$DEST")"

echo "Fetching published Zygisk API header at ${PINNED_COMMIT}"
curl --fail --location --proto '=https' --tlsv1.2 "$URL" --output "$DEST.tmp"

# The header is pinned by commit. Add an expected SHA-256 before release packaging
# so a build never trusts downloaded bytes solely because the URL succeeded.
if [[ -n "$EXPECTED_SHA256" ]]; then
  printf '%s  %s\n' "$EXPECTED_SHA256" "$DEST.tmp" | sha256sum --check --status
fi

mv "$DEST.tmp" "$DEST"
echo "Wrote $DEST"
