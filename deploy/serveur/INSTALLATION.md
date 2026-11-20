# Installation sur le serveur Proxmox

Application interne de génération (`https://generation.karta-transit.ci`), servie par un tunnel Cloudflare et protégée par Cloudflare Access. Aucun port n'est ouvert sur le réseau.

## 1. VM ou LXC Debian avec Docker

1. Sur Proxmox, créer une VM Debian 12 avec les caractéristiques suivantes :

   | Élément | Recommandé | Minimum |
   |---|---|---|
   | Type | VM | LXC avec `nesting=1` et `keyctl=1` |
   | Processeur | 2 vCPU | 2 vCPU |
   | Mémoire | 4 Go | 2 Go |
   | Disque | 50 Go (extensible) | 20 Go |
   | Réseau | sortie HTTPS vers Internet, aucun port entrant | |

   Pourquoi : l'application tourne en un seul processus (un vCPU sert aux générations, l'autre au système, à Docker et au tunnel ; plus de vCPU n'accélère pas une génération). Une génération de 300 motos prend environ 20 s de calcul et 300 Mo de mémoire : 4 Go laissent plusieurs collègues générer en même temps. Un dossier occupe environ 15 Mo (PDF 0,25 Mo, XML 2,3 Mo et corps 0,2 Mo par génération, environ trois générations, doublées par le miroir de sauvegarde), soit environ 1,5 Go par mois pour 100 dossiers : 50 Go donnent environ deux ans et demi de marge après le système et Docker (environ 6 Go). Une VM fait tourner Docker sans réglage particulier ; un LXC demande l'imbrication et isole moins.
2. Installer Docker Engine et le plugin Compose en suivant https://docs.docker.com/engine/install/debian/ puis vérifier : `docker compose version`.
3. Récupérer le dépôt (branche de production) : `git clone <url-du-dépôt> /opt/generation && cd /opt/generation/deploy/serveur`.
4. Créer le dossier des données : `mkdir -p data`. Il est monté dans le conteneur sur `/app/data` et contient `webapp/webapp.db`, `webapp/dossiers/`, `chassis_registry.db` et `sauvegardes/` (voir §6 pour l'espace disque et la copie hors serveur). Le conteneur tourne avec l'UID 1000 : `chown -R 1000:1000 data`.

## 2. Tunnel et nom d'hôte (compte Cloudflare Karta, zone `karta-transit.ci`)

1. Zero Trust > Networks > Tunnels > Create a tunnel > Cloudflared, nom par exemple `generation`.
2. Copier le jeton du tunnel (valeur de `TUNNEL_TOKEN`) : il sera mis dans `.env`, jamais dans le dépôt.
3. Onglet Public Hostname : nom d'hôte `generation.karta-transit.ci`, service `HTTP` et URL `app:8000`.
4. Ne pas renseigner `httpHostHeader` (ni « HTTP Host Header » dans les réglages additionnels) : le contrôle CSRF de l'app compare l'hôte de l'en-tête `Origin` au `Host` reçu, qui doit rester le nom public.

## 3. Application Access

1. Zero Trust > Access > Applications > Add an application > Self-hosted.
2. Domaine : `generation.karta-transit.ci`. Équipe : `groupekarta.cloudflareaccess.com`.
3. Politique Allow, règle Emails : les adresses e-mail de l'équipe autorisée.
4. Récupérer l'AUD : Access > Applications > l'application > Configure > Overview > « Application Audience (AUD) Tag ». Cette valeur est `WEBAPP_ACCESS_AUD`.

## 4. Fichier `.env`

```
cp .env.exemple .env && chmod 600 .env
```

Renseigner `WEBAPP_ACCESS_AUD`, `WEBAPP_ADMINS` (e-mails des administrateurs séparés par des virgules) et `TUNNEL_TOKEN`, tous trois obligatoires (le compose refuse de démarrer sinon). Ne pas définir `WEBAPP_DEV_USER` : l'application refuse de démarrer si cette variable est présente avec l'AUD.

API historique `/api/v1/*` : elle n'est pas utilisée. Avec Access configuré, ces routes exigent le jeton Access et aussi l'en-tête `X-API-Key`. Pour la garder fermée, ne pas définir `API_KEYS` (ou y mettre une clé longue et aléatoire) ; ne rien ajouter d'autre dans `.env`.

## 5. Démarrage

```
docker compose up -d --build
docker compose ps
docker compose logs -f app
```

L'application tourne avec un seul worker uvicorn (le verrou de déclaration est propre à chaque processus) : ne jamais ajouter `--workers` ni lancer plusieurs instances de `app`.

## 6. Sauvegarde (cron)

`sauvegarde.sh` écrit dans `data/sauvegardes/` :

- une copie datée à chaud de `webapp.db` et de `chassis_registry.db` (`sqlite3 .backup`), supprimée après 30 jours ;
- `dossiers-miroir/` : miroir incrémental de `data/webapp/dossiers/` (`rsync -a`, sans `--delete`). Les fichiers d'un dossier ne sont jamais réécrits : chaque nuit seuls les nouveaux fichiers sont copiés et rien n'est retiré du miroir ;
- si la variable `BACKUP_REMOTE` est définie (destination rsync, par exemple `sauvegarde@nas:/sauvegardes/generation/`), une copie de tout `data/sauvegardes/` hors du serveur. Le script sort en erreur si cette copie échoue.

**La copie hors serveur est indispensable** (R2 ou rsync, ci-dessous) : `data/sauvegardes/` est sur le même disque que les données et ne protège pas d'une perte du disque ou de la VM.

### Copie hors serveur sur Cloudflare R2 (retenue pour Karta)

`sauvegarde-r2.sh`, lancé sur l'hôte par l'utilisateur qui gère le compose (membre du groupe `docker`, sans `sudo`) :

1. exécute `sauvegarde.sh` dans le conteneur (copie locale ci-dessus) ;
2. envoie `data/sauvegardes/` vers R2 avec rclone, dans un conteneur jetable (`rclone/rclone`, rien à installer sur l'hôte). `rclone copy` ne supprime jamais rien sur R2.

Mise en place :

1. Bucket `karta-generation-backups`, avec des règles de cycle de vie : copies des bases (`generation/webapp-*`, `generation/chassis_registry-*`) supprimées après 90 jours ; les fichiers des dossiers (`generation/dossiers-miroir/`) sont conservés.
2. Tableau de bord Cloudflare > R2 > Manage API tokens > Create Account API token : permission **Object Read & Write**, limitée au bucket `karta-generation-backups`. Noter l'Access Key ID, le Secret Access Key et l'endpoint S3 (`https://<id du compte>.r2.cloudflarestorage.com`).
3. Sur la VM, à côté de `docker-compose.yml`, créer `r2.env` (droits 600, ignoré par git) :
   ```
   RCLONE_CONFIG_R2_ACCESS_KEY_ID=<Access Key ID>
   RCLONE_CONFIG_R2_SECRET_ACCESS_KEY=<Secret Access Key>
   RCLONE_CONFIG_R2_ENDPOINT=https://<id du compte>.r2.cloudflarestorage.com
   ```
4. Lancer une fois à la main, puis ajouter au `crontab -e` de cet utilisateur :
   ```
   0 2 * * * BACKUP_R2=karta-generation-backups/generation /opt/generation/deploy/serveur/sauvegarde-r2.sh >> /opt/generation/deploy/serveur/sauvegarde.log 2>&1
   ```
5. Restauration : `docker run --rm --env-file r2.env -e RCLONE_CONFIG_R2_TYPE=s3 -e RCLONE_CONFIG_R2_PROVIDER=Cloudflare -v /tmp/restauration:/r rclone/rclone:1.68.2 copy r2:karta-generation-backups/generation /r`.

### Copie hors serveur par rsync (NAS ou autre serveur)

Le script s'exécute sur l'hôte (VM ou LXC), qui porte la clé SSH vers la destination :

1. Installer les outils : `apt install sqlite3 rsync openssh-client`.
2. Créer une clé SSH sans phrase de passe pour root : `ssh-keygen -t ed25519 -f /root/.ssh/sauvegarde -N ""`, puis ajouter `/root/.ssh/sauvegarde.pub` aux clés autorisées du compte de sauvegarde du NAS (ou du serveur de destination).
3. Dans `/root/.ssh/config` :
   ```
   Host nas
     HostName <adresse du NAS>
     User sauvegarde
     IdentityFile /root/.ssh/sauvegarde
   ```
   puis vérifier une première fois à la main (empreinte de l'hôte acceptée) : `ssh nas true`.
4. Lancer le script une fois à la main, puis l'ajouter dans `crontab -e` de root :

```
30 2 * * * DATA_DIR=/opt/generation/deploy/serveur/data BACKUP_REMOTE=nas:/sauvegardes/generation/ /opt/generation/deploy/serveur/sauvegarde.sh >> /var/log/generation-sauvegarde.log 2>&1
```

Sans `BACKUP_REMOTE`, seule la copie locale est faite. Le script peut aussi tourner dans le conteneur (`sqlite3` et `rsync` sont dans l'image), pour la copie locale seulement : `docker compose exec -T app bash /app/sauvegarde.sh`.

La destination distante n'est jamais purgée par le script (pas de `--delete`) : sa rétention se règle sur le NAS.

Espace disque : `data/` et `data/sauvegardes/` grossissent avec le nombre de dossiers (PDF et générations, plus le miroir qui en double la taille, plus 30 copies de chaque base). Compter environ 15 Mo par dossier (1,5 Go par mois pour 100 dossiers). Surveiller le disque avec `df -h /opt/generation` (par exemple chaque mois) et agrandir le disque Proxmox avant 80 % d'occupation.

## 7. Arrêt de l'instance Render

Une fois la section « Vérifier » validée : dans le tableau de bord Render, supprimer le service. Le fichier `render.yaml` reste dans le dépôt, sans effet.

## Vérifier

1. Ouvrir `https://generation.karta-transit.ci` : la page de connexion Cloudflare Access s'affiche ; se connecter avec une adresse autorisée.
2. L'application s'ouvre ; déposer un RFCV de test et vérifier que la génération aboutit.
3. Sans connexion Access, l'accès doit être refusé ; `docker compose ps` ne doit montrer aucun port publié.

## Mettre à jour

```
cd /opt/generation && git pull
cd deploy/serveur && docker compose up -d --build
```

Les données (`data/`) sont conservées.
