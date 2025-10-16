# Docker Deployment Guide

Guide complet pour déployer l'API Convertisseur PDF RFCV → XML ASYCUDA avec Docker.

## Table des matières

- [Prérequis](#prérequis)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Développement](#développement)
- [Production](#production)
- [Commandes utiles](#commandes-utiles)
- [Volumes et persistance](#volumes-et-persistance)
- [Monitoring et logs](#monitoring-et-logs)
- [Troubleshooting](#troubleshooting)
- [Architecture](#architecture)

## Prérequis

- Docker >= 20.10
- Docker Compose >= 2.0
- 2GB RAM minimum
- 5GB espace disque

## Quick Start

### 1. Configuration initiale

```bash
# Cloner le repository
git clone <repository-url>
cd pdf-xml-asycuda

# Copier l'exemple de configuration
cp .env.example .env

# Éditer la configuration (optionnel)
nano .env
```

### 2. Lancer l'API (Production)

```bash
# Build et démarrage
docker-compose up -d

# Vérifier les logs
docker-compose logs -f api

# L'API est accessible sur http://localhost:8000
```

### 3. Vérifier le déploiement

```bash
# Health check
curl http://localhost:8000/api/v1/health

# Documentation
open http://localhost:8000/docs
```

## Configuration

### Variables d'environnement

Éditez le fichier `.env` pour personnaliser la configuration :

```bash
# API Configuration
API_TITLE="API Convertisseur PDF RFCV → XML ASYCUDA"
API_VERSION="1.0.0"
API_DEBUG=False

# Server
API_HOST="0.0.0.0"
API_PORT=8000

# CORS (ajuster selon vos besoins)
API_CORS_ORIGINS=["http://localhost:3000"]

# Storage
API_UPLOAD_DIR="uploads"
API_OUTPUT_DIR="output"
API_MAX_UPLOAD_SIZE=52428800  # 50MB

# Job Management
API_JOB_EXPIRY_HOURS=24
API_CLEANUP_INTERVAL_HOURS=6

# Batch Processing
API_DEFAULT_WORKERS=4
API_MAX_WORKERS=8

# Rate Limiting
API_RATE_LIMIT_ENABLED=False
API_RATE_LIMIT_PER_MINUTE=60

# Docker
DOCKER_IMAGE_TAG=latest
```

### Fichiers de configuration

| Fichier | Description |
|---------|-------------|
| `Dockerfile` | Image Docker multi-stage optimisée |
| `docker-compose.yml` | Configuration production |
| `docker-compose.dev.yml` | Override pour développement |
| `.dockerignore` | Fichiers exclus de l'image |
| `.env` | Variables d'environnement (à créer) |

## Développement

Le mode développement active :
- Hot reload automatique
- Mode debug
- Logs verbeux
- Volume mount du code source

### Lancer en mode développement

```bash
# Build et démarrage avec hot reload
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up

# Ou en détaché
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# Logs en temps réel
docker-compose logs -f api
```

### Développement avec rebuild

```bash
# Rebuild complet
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up --build

# Rebuild sans cache
docker-compose -f docker-compose.yml -f docker-compose.dev.yml build --no-cache
```

### Exécuter les tests

```bash
# Tests dans le container
docker-compose exec api pytest tests/ -v

# Tests avec couverture
docker-compose exec api pytest tests/api/ --cov=src/api --cov-report=html

# Shell interactif
docker-compose exec api bash
```

## Production

### Build de l'image

```bash
# Build local
docker-compose build

# Build avec tag spécifique
DOCKER_IMAGE_TAG=v1.0.0 docker-compose build

# Build multi-plateforme (amd64, arm64)
docker buildx build --platform linux/amd64,linux/arm64 -t pdf-xml-asycuda-api:latest .
```

### Déploiement

```bash
# Démarrer en production
docker-compose up -d

# Redémarrage
docker-compose restart

# Arrêt propre
docker-compose down

# Arrêt avec suppression des volumes
docker-compose down -v
```

### Mise à jour

```bash
# Pull nouvelle image
docker-compose pull

# Redéployer avec nouvelle image
docker-compose up -d --force-recreate

# Ou rebuild et redéployer
docker-compose up -d --build
```

### Scaling (futur)

```bash
# Scaler à 3 instances (nécessite load balancer)
docker-compose up -d --scale api=3
```

## Commandes utiles

### Gestion des containers

```bash
# Lister les containers
docker-compose ps

# Logs en temps réel
docker-compose logs -f api

# Logs avec timestamp
docker-compose logs -f --timestamps api

# Shell dans le container
docker-compose exec api bash

# Exécuter une commande
docker-compose exec api python -c "print('Hello')"

# Redémarrer un service
docker-compose restart api

# Arrêter un service
docker-compose stop api

# Supprimer les containers
docker-compose down
```

### Gestion des images

```bash
# Lister les images
docker images | grep pdf-xml-asycuda

# Supprimer les images
docker rmi pdf-xml-asycuda-api:latest

# Nettoyer les images inutilisées
docker image prune -a

# Exporter une image
docker save pdf-xml-asycuda-api:latest | gzip > api-image.tar.gz

# Importer une image
docker load < api-image.tar.gz
```

### Gestion des volumes

```bash
# Lister les volumes
docker volume ls | grep pdf-xml-asycuda

# Inspecter un volume
docker volume inspect pdf-xml-asycuda-uploads

# Supprimer les volumes
docker volume rm pdf-xml-asycuda-uploads pdf-xml-asycuda-outputs

# Nettoyer les volumes inutilisés
docker volume prune
```

## Volumes et persistance

### Volumes définis

| Volume | Path dans container | Description |
|--------|---------------------|-------------|
| `pdf-xml-asycuda-uploads` | `/app/uploads` | Fichiers PDF uploadés |
| `pdf-xml-asycuda-outputs` | `/app/output` | Fichiers XML générés |

### Backup des volumes

```bash
# Backup uploads
docker run --rm -v pdf-xml-asycuda-uploads:/data -v $(pwd):/backup \
  alpine tar czf /backup/uploads-backup.tar.gz -C /data .

# Backup outputs
docker run --rm -v pdf-xml-asycuda-outputs:/data -v $(pwd):/backup \
  alpine tar czf /backup/outputs-backup.tar.gz -C /data .
```

### Restore des volumes

```bash
# Restore uploads
docker run --rm -v pdf-xml-asycuda-uploads:/data -v $(pwd):/backup \
  alpine tar xzf /backup/uploads-backup.tar.gz -C /data

# Restore outputs
docker run --rm -v pdf-xml-asycuda-outputs:/data -v $(pwd):/backup \
  alpine tar xzf /backup/outputs-backup.tar.gz -C /data
```

### Accès aux fichiers

```bash
# Copier un fichier du container vers l'hôte
docker cp pdf-xml-asycuda-api:/app/output/file.xml ./local-file.xml

# Copier un fichier de l'hôte vers le container
docker cp ./local-file.pdf pdf-xml-asycuda-api:/app/uploads/
```

## Monitoring et logs

### Health checks

```bash
# Vérifier le status
docker-compose ps

# Health check manuel
curl http://localhost:8000/api/v1/health

# Métriques système
curl http://localhost:8000/api/v1/metrics
```

### Logs

```bash
# Logs en temps réel
docker-compose logs -f api

# Dernières 100 lignes
docker-compose logs --tail=100 api

# Logs depuis 1 heure
docker-compose logs --since 1h api

# Export des logs
docker-compose logs api > api-logs.txt
```

### Métriques container

```bash
# Stats en temps réel
docker stats pdf-xml-asycuda-api

# Utilisation mémoire/CPU
docker-compose top api

# Inspecter le container
docker inspect pdf-xml-asycuda-api
```

## Troubleshooting

### Container ne démarre pas

```bash
# Vérifier les logs
docker-compose logs api

# Vérifier la configuration
docker-compose config

# Rebuild complet
docker-compose down
docker-compose build --no-cache
docker-compose up
```

### Problèmes de permissions

```bash
# Le container tourne avec UID 1000
# Vérifier les permissions des volumes
docker volume inspect pdf-xml-asycuda-uploads

# Ajuster les permissions si nécessaire
docker-compose exec api chown -R appuser:appuser /app/uploads /app/output
```

### Problèmes de réseau

```bash
# Vérifier le network
docker network ls | grep pdf-xml-asycuda
docker network inspect pdf-xml-asycuda-network

# Recréer le network
docker-compose down
docker network prune
docker-compose up -d
```

### Image trop volumineuse

```bash
# Vérifier la taille
docker images pdf-xml-asycuda-api

# Analyser les layers
docker history pdf-xml-asycuda-api:latest

# L'image devrait faire ~150-200MB avec multi-stage build
```

### Port déjà utilisé

```bash
# Changer le port dans .env
API_PORT=8001

# Ou dans docker-compose override
docker-compose -f docker-compose.yml -f docker-compose.override.yml up
```

### Nettoyage complet

```bash
# Tout supprimer (containers, volumes, images)
docker-compose down -v --rmi all

# Nettoyer le système Docker
docker system prune -a --volumes
```

## Architecture

### Structure de l'image Docker

```
Image: python:3.11-slim-bookworm (~150MB)
├── Stage 1: Builder
│   ├── Compilation des dépendances
│   └── Création du venv
├── Stage 2: Runtime
│   ├── Copie du venv
│   ├── Code application
│   ├── User non-root (UID 1000)
│   └── Healthcheck intégré
```

### Architecture du déploiement

```
┌─────────────────────────────────────┐
│  Docker Host                        │
│                                     │
│  ┌───────────────────────────────┐ │
│  │  Container: api                │ │
│  │  Port: 8000                    │ │
│  │                                │ │
│  │  ┌──────────────────────────┐ │ │
│  │  │  FastAPI Application     │ │ │
│  │  │  - Conversion endpoints  │ │ │
│  │  │  - Batch processing      │ │ │
│  │  │  - File management       │ │ │
│  │  └──────────────────────────┘ │ │
│  │                                │ │
│  │  Volumes:                      │ │
│  │  - uploads/  (persistent)     │ │
│  │  - output/   (persistent)     │ │
│  └───────────────────────────────┘ │
│                                     │
│  Network: pdf-xml-asycuda-network  │
└─────────────────────────────────────┘
```

### Sécurité

- ✅ Image multi-stage (taille réduite)
- ✅ User non-root (UID 1000)
- ✅ Minimal packages installés
- ✅ Healthcheck intégré
- ✅ Volumes isolés
- ✅ Network isolé
- ✅ Logs rotation
- ✅ Variables d'environnement séparées

### Performance

- Image optimisée: ~150MB
- Build time: ~2-3 minutes (première fois)
- Build time: ~30s (avec cache)
- Startup time: ~5-10s
- Memory usage: ~200-300MB
- CPU usage: Variable selon charge

## Support

Pour toute question ou problème :

1. Vérifier les logs: `docker-compose logs -f api`
2. Consulter la [documentation principale](README.md)
3. Ouvrir une issue sur le repository

## Licence

Voir [LICENSE](LICENSE)
