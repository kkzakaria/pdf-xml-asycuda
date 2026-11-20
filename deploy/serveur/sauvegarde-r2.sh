#!/usr/bin/env bash
# Sauvegarde nocturne avec copie hors serveur sur Cloudflare R2. À lancer sur l'hôte (cron de
# l'utilisateur qui gère le compose, membre du groupe docker ; voir INSTALLATION.md §6) :
#   BACKUP_R2=karta-generation-backups/generation /opt/generation/deploy/serveur/sauvegarde-r2.sh
#
# 1. Copie locale dans le conteneur (sauvegarde.sh : bases datées + miroir des dossiers, écrits
#    sous data/sauvegardes/ par l'utilisateur du conteneur) ;
# 2. envoi de data/sauvegardes/ vers R2 par rclone, dans un conteneur jetable (rien à installer
#    sur l'hôte). « rclone copy » ajoute ou met à jour les fichiers et ne supprime jamais rien sur
#    R2 : la rétention se règle par les règles de cycle de vie du bucket.
#
# Identifiants R2 dans R2_ENV (défaut : r2.env à côté de ce script, droits 600, jamais dans le
# dépôt) :
#   RCLONE_CONFIG_R2_ACCESS_KEY_ID=...
#   RCLONE_CONFIG_R2_SECRET_ACCESS_KEY=...
#   RCLONE_CONFIG_R2_ENDPOINT=https://<id du compte>.r2.cloudflarestorage.com
# Code de sortie non nul si une étape échoue.
set -euo pipefail

cd "$(dirname "$(readlink -f "$0")")"
BACKUP_R2="${BACKUP_R2:?BACKUP_R2 requis (bucket/préfixe, ex. karta-generation-backups/generation)}"
R2_ENV="${R2_ENV:-$PWD/r2.env}"
RCLONE_IMAGE="${RCLONE_IMAGE:-rclone/rclone:1.68.2}"

[ -r "$R2_ENV" ] || { echo "Identifiants R2 introuvables : $R2_ENV" >&2; exit 1; }

docker compose exec -T app bash /app/sauvegarde.sh

if ! docker run --rm --env-file "$R2_ENV" \
    -e RCLONE_CONFIG_R2_TYPE=s3 -e RCLONE_CONFIG_R2_PROVIDER=Cloudflare \
    -v "$PWD/data/sauvegardes:/sauvegardes:ro" \
    "$RCLONE_IMAGE" copy /sauvegardes "r2:$BACKUP_R2" --s3-no-check-bucket; then
  echo "Copie R2 échouée : $BACKUP_R2" >&2
  exit 1
fi
echo "Copie R2 OK : $BACKUP_R2 ($(date +%Y%m%d-%H%M%S))"
