#!/usr/bin/env bash
# Sauvegarde à chaud : webapp.db et chassis_registry.db (sqlite3 .backup) + archive de dossiers/.
# Rétention 30 jours. Code de sortie non nul en cas d'échec.
# Exécutée depuis l'hôte via le conteneur (sqlite3 est dans l'image) :
#   cd /opt/generation/deploy/serveur && docker compose exec -T app bash /app/sauvegarde.sh
# ou directement : DATA_DIR=./data ./sauvegarde.sh  (nécessite sqlite3 sur l'hôte)
set -euo pipefail

DATA_DIR="${DATA_DIR:-/app/data}"
DEST="${DEST:-$DATA_DIR/sauvegardes}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
STAMP="$(date +%Y%m%d-%H%M%S)"

command -v sqlite3 >/dev/null || { echo "sqlite3 introuvable" >&2; exit 1; }
mkdir -p "$DEST"

for db in webapp/webapp.db chassis_registry.db; do
  src="$DATA_DIR/$db"
  [ -f "$src" ] || { echo "Base absente : $src" >&2; exit 1; }
  out="$DEST/$(basename "${db%.db}")-$STAMP.db"
  sqlite3 "$src" ".backup '$out'"
  [ -s "$out" ] || { echo "Sauvegarde vide : $out" >&2; exit 1; }
done

if [ -d "$DATA_DIR/webapp/dossiers" ]; then
  tar -czf "$DEST/dossiers-$STAMP.tar.gz" -C "$DATA_DIR/webapp" dossiers
fi

find "$DEST" -maxdepth 1 -type f \( -name '*.db' -o -name '*.tar.gz' \) -mtime +"$RETENTION_DAYS" -delete
echo "Sauvegarde OK : $DEST ($STAMP)"
