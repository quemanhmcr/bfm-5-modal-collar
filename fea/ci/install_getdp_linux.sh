#!/usr/bin/env bash
set -euo pipefail

VERSION="3.5.0"
ARCHIVE="getdp-${VERSION}-Linux64c.tgz"
URL="https://www.getdp.info/bin/Linux/${ARCHIVE}"
SHA256="d3c28fa18f20d6147b4c7367d4dd802e9f7ddb58c608688bbb71919dbca8041d"
INSTALL_ROOT="${1:-${GITHUB_WORKSPACE:-$PWD}/.cache/fea3d/getdp-${VERSION}-Linux64}"

if [[ -x "$INSTALL_ROOT/bin/getdp" ]]; then
  "$INSTALL_ROOT/bin/getdp" -version
  exit 0
fi

mkdir -p "$(dirname "$INSTALL_ROOT")"
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT
curl --fail --location --retry 5 --retry-delay 2 "$URL" -o "$tmp_dir/$ARCHIVE"
echo "$SHA256  $tmp_dir/$ARCHIVE" | sha256sum --check --strict
mkdir -p "$tmp_dir/unpack"
tar -xzf "$tmp_dir/$ARCHIVE" -C "$tmp_dir/unpack"
source_root="$tmp_dir/unpack/getdp-${VERSION}-Linux64"
[[ -x "$source_root/bin/getdp" ]]
rm -rf "$INSTALL_ROOT"
mv "$source_root" "$INSTALL_ROOT"
"$INSTALL_ROOT/bin/getdp" -version
