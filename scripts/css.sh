#!/usr/bin/env bash
# Compile le CSS de la webapp avec le CLI autonome Tailwind (sans Node) :
#   src/webapp/styles/app.css  ->  src/webapp/static/app.css (minifié, non versionné)
# Usage : scripts/css.sh [--watch]
# Le binaire épinglé est téléchargé une fois dans .cache/ et sa somme SHA-256 est vérifiée.
set -euo pipefail

TAILWIND_VERSION="v4.3.5"

# Binaire tailwindcss-<plateforme> et sa somme SHA-256 (page de la version sur GitHub).
# Pas de tableau associatif ni de readlink -f : compatible avec le bash 3.2 de macOS.
case "$(uname -s)-$(uname -m)" in
  Linux-x86_64)
    PLATEFORME="linux-x64";   SHA256="e47695cee3f0d90623a91f3939b08bdee610eb5ad99340adff9d4145b284d6cc" ;;
  Linux-aarch64|Linux-arm64)
    PLATEFORME="linux-arm64"; SHA256="ffcd0d21dbd7c605dc12743ff0c0b47debc963c86b399674084c1c8f2c96ecad" ;;
  Darwin-x86_64)
    PLATEFORME="macos-x64";   SHA256="a63702686a3ed048b3135d84a73be49ea9d47f880c9b20e54b3ef60934ad8cdf" ;;
  Darwin-arm64)
    PLATEFORME="macos-arm64"; SHA256="f3f4f5d1727e2b693b8f1c9a1492b5dd87008c86ea286bee1589cb458e6235fc" ;;
  *) echo "Plateforme non prise en charge : $(uname -s)-$(uname -m)" >&2; exit 1 ;;
esac
# (tailwindcss-linux-x64, tailwindcss-linux-arm64, tailwindcss-macos-x64, tailwindcss-macos-arm64)

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BIN="$ROOT/.cache/tailwindcss-$TAILWIND_VERSION-$PLATEFORME"

somme() {   # SHA-256 d'un fichier, avec sha256sum (Linux) ou shasum (macOS)
  if command -v sha256sum >/dev/null; then sha256sum "$1"; else shasum -a 256 "$1"; fi | cut -d' ' -f1
}

if [ ! -x "$BIN" ]; then
  mkdir -p "$ROOT/.cache"
  curl -fsSL -o "$BIN.tmp" \
    "https://github.com/tailwindlabs/tailwindcss/releases/download/$TAILWIND_VERSION/tailwindcss-$PLATEFORME"
  if [ "$(somme "$BIN.tmp")" != "$SHA256" ]; then
    rm -f "$BIN.tmp"; echo "Somme SHA-256 du binaire Tailwind incorrecte" >&2; exit 1
  fi
  chmod +x "$BIN.tmp" && mv "$BIN.tmp" "$BIN"
fi

cd "$ROOT/src/webapp"
exec "$BIN" -i styles/app.css -o static/app.css --minify "$@"
