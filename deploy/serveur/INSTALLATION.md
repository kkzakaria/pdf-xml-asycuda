# Installation sur le serveur Proxmox

Application interne de génération (`https://generation.karta-transit.ci`), servie par un tunnel Cloudflare et protégée par Cloudflare Access. Aucun port n'est ouvert sur le réseau.

## 1. VM ou LXC Debian avec Docker

1. Sur Proxmox, créer une VM (ou un LXC avec `nesting=1` et `keyctl=1`) Debian 12, 2 vCPU, 2 Go de RAM, 20 Go de disque.
2. Installer Docker Engine et le plugin Compose en suivant https://docs.docker.com/engine/install/debian/ puis vérifier : `docker compose version`.
3. Récupérer le dépôt (branche de production) : `git clone <url-du-dépôt> /opt/generation && cd /opt/generation/deploy/serveur`.
4. Créer le dossier des données : `mkdir -p data`. Il est monté dans le conteneur sur `/app/data` et contient `webapp/webapp.db`, `webapp/dossiers/`, `chassis_registry.db` et `sauvegardes/`. Le conteneur tourne avec l'UID 1000 : `chown -R 1000:1000 data`.

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

`sauvegarde.sh` copie à chaud `webapp.db` et `chassis_registry.db` (`sqlite3 .backup`), archive `dossiers/`, écrit dans `data/sauvegardes/` avec horodatage, supprime ce qui a plus de 30 jours, et sort en erreur si un échec survient. Elle s'exécute dans le conteneur (sqlite3 est dans l'image, le script y est monté). Ajouter dans `crontab -e` (utilisateur membre du groupe docker) :

```
30 2 * * * cd /opt/generation/deploy/serveur && docker compose exec -T app bash /app/sauvegarde.sh >> /var/log/generation-sauvegarde.log 2>&1
```

Copier régulièrement `data/sauvegardes/` hors du serveur (NAS, Proxmox Backup).

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
