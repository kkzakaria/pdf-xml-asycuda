#!/usr/bin/env bash
# Compile le CSS de la webapp avec le CLI autonome Tailwind (sans Node) :
#   src/webapp/styles/app.css  ->  src/webapp/static/app.css (minifié, non versionné)
# Usage : scripts/css.sh [--watch]
# Le binaire épinglé est téléchargé une fois dans .cache/ et sa somme SHA-256 est vérifiée.
set -euo pipefail

TAILWIND_VERSION="v4.3.5"
TAILWIND_SHA256="e47695cee3f0d90623a91f3939b08bdee610eb5ad99340adff9d4145b284d6cc"   # tailwindcss-linux-x64

ROOT="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"
BIN="$ROOT/.cache/tailwindcss-$TAILWIND_VERSION"

case "$(uname -s)-$(uname -m)" in
  Linux-x86_64) ;;
  *) echo "Plateforme non prise en charge par ce script : $(uname -s)-$(uname -m)" >&2; exit 1 ;;
esac

if [ ! -x "$BIN" ]; then
  mkdir -p "$ROOT/.cache"
  curl -fsSL -o "$BIN.tmp" \
    "https://github.com/tailwindlabs/tailwindcss/releases/download/$TAILWIND_VERSION/tailwindcss-linux-x64"
  echo "$TAILWIND_SHA256  $BIN.tmp" | sha256sum -c --quiet - \
    || { rm -f "$BIN.tmp"; echo "Somme SHA-256 du binaire Tailwind incorrecte" >&2; exit 1; }
  chmod +x "$BIN.tmp" && mv "$BIN.tmp" "$BIN"
fi

cd "$ROOT/src/webapp"
exec "$BIN" -i styles/app.css -o static/app.css --minify "$@"
