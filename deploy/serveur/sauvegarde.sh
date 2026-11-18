#!/usr/bin/env bash
# Sauvegarde à chaud :
# - webapp.db et chassis_registry.db : copies datées (sqlite3 .backup), rétention 30 jours ;
# - dossiers/ : miroir incrémental (rsync, sans --delete : les fichiers d'un dossier ne sont
#   jamais réécrits, rien n'est jamais retiré du miroir) ;
# - si BACKUP_REMOTE est défini (destination rsync, ex. sauvegarde@nas:/sauvegardes/generation/),
#   copie de tout le dossier des sauvegardes hors du serveur.
# Code de sortie non nul en cas d'échec. Nécessite sqlite3 et rsync (+ ssh pour une destination
# distante) là où le script s'exécute. Sur l'hôte (recommandé, voir INSTALLATION.md §6) :
#   DATA_DIR=/opt/generation/deploy/serveur/data BACKUP_REMOTE=... ./sauvegarde.sh
# ou dans le conteneur (copie locale seulement, sans clé SSH) :
#   cd /opt/generation/deploy/serveur && docker compose exec -T app bash /app/sauvegarde.sh
set -euo pipefail

DATA_DIR="${DATA_DIR:-/app/data}"
DEST="${DEST:-$DATA_DIR/sauvegardes}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
BACKUP_REMOTE="${BACKUP_REMOTE:-}"
STAMP="$(date +%Y%m%d-%H%M%S)"

command -v sqlite3 >/dev/null || { echo "sqlite3 introuvable" >&2; exit 1; }
command -v rsync >/dev/null || { echo "rsync introuvable" >&2; exit 1; }
mkdir -p "$DEST"

for db in webapp/webapp.db chassis_registry.db; do
  src="$DATA_DIR/$db"
  [ -f "$src" ] || { echo "Base absente : $src" >&2; exit 1; }
  out="$DEST/$(basename "${db%.db}")-$STAMP.db"
  sqlite3 "$src" ".backup '$out'"
  [ -s "$out" ] || { echo "Sauvegarde vide : $out" >&2; exit 1; }
done

if [ -d "$DATA_DIR/webapp/dossiers" ]; then
  mkdir -p "$DEST/dossiers-miroir"
  rsync -a "$DATA_DIR/webapp/dossiers/" "$DEST/dossiers-miroir/"
fi

# Copies datées des bases (et anciennes archives .tar.gz des versions précédentes du script)
find "$DEST" -maxdepth 1 -type f \( -name '*.db' -o -name '*.tar.gz' \) -mtime +"$RETENTION_DAYS" -delete

if [ -n "$BACKUP_REMOTE" ]; then
  if ! rsync -a "$DEST/" "$BACKUP_REMOTE"; then
    echo "Copie hors serveur échouée : $BACKUP_REMOTE" >&2
    exit 1
  fi
  echo "Copie hors serveur OK : $BACKUP_REMOTE"
fi
echo "Sauvegarde OK : $DEST ($STAMP)"
