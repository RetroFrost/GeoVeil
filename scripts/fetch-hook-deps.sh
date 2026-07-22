#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
THIRD_PARTY="$ROOT/native/third_party"
LSPLANT_COMMIT="a0990196c26e3fad57213a03af22dbf993396c8a"
DOBBY_COMMIT="05a09ac6807a6bb1726350e40ea4b127c1c79809"

fetch_repo() {
  local url=$1
  local commit=$2
  local destination=$3

  if [[ -d "$destination/.git" ]] && [[ "$(git -C "$destination" rev-parse HEAD)" == "$commit" ]]; then
    git -C "$destination" submodule update --init --recursive
    return
  fi

  rm -rf "$destination"
  git init -q "$destination"
  git -C "$destination" remote add origin "$url"
  git -C "$destination" fetch --depth=1 origin "$commit"
  git -C "$destination" checkout -q --detach FETCH_HEAD
  git -C "$destination" submodule update --init --recursive
  [[ "$(git -C "$destination" rev-parse HEAD)" == "$commit" ]]
}

mkdir -p "$THIRD_PARTY"
fetch_repo https://github.com/JingMatrix/LSPlant.git "$LSPLANT_COMMIT" "$THIRD_PARTY/lsplant"
fetch_repo https://github.com/JingMatrix/Dobby.git "$DOBBY_COMMIT" "$THIRD_PARTY/dobby"

printf 'LSPlant %s\nDobby %s\n' "$LSPLANT_COMMIT" "$DOBBY_COMMIT" \
  > "$THIRD_PARTY/hook-dependencies.lock"

echo "Fetched pinned LSPlant and Dobby sources"
