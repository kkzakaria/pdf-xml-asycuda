# Changelog

Toutes les modifications notables de ce projet seront documentées dans ce fichier.

Le format est basé sur [Keep a Changelog](https://keepachangelog.com/fr/1.0.0/),
et ce projet adhère au [Semantic Versioning](https://semver.org/lang/fr/).

## [1.1.0] - 2025-10-17

### 🔒 Sécurité - Version Sécurisée Production-Ready

Cette version majeure implémente une sécurisation complète de l'API, la rendant prête pour un déploiement en production.

#### Ajouté

**Authentification & Autorisation**
- Authentification API Key obligatoire par défaut (`API_REQUIRE_AUTHENTICATION=true`)
- Support multi-clés pour rotation sans interruption
- Protection contre timing attacks avec `secrets.compare_digest()`
- Génération de clés sécurisées avec `secrets.token_urlsafe(32)`
- Support Swagger UI avec bouton "Authorize" pour tests interactifs
- Schéma OpenAPI personnalisé avec `APIKeyHeader` security scheme

**Protection DDoS & Abus**
- Rate limiting avec slowapi (configurable par endpoint)
  - Uploads individuels: 10/minute
  - Uploads async: 20/minute
  - Batch processing: 5/heure
  - Endpoints publics: 120/minute
- Rate limit headers (`X-RateLimit-*`) dans les réponses
- Messages d'erreur 429 avec `Retry-After` header

**Validation & Sanitisation**
- Protection path traversal multi-couches
- Validation stricte des file_id (regex + path resolution)
- Sanitisation complète des noms de fichiers
- Validation taille fichiers avec lecture par chunks (50MB max)
- Validation magic number PDF
- Validation stricte des paramètres d'entrée

**Sécurité CORS**
- CORS restrictif par défaut (liste vide d'origines)
- Credentials désactivés par défaut
- Méthodes limitées (GET, POST uniquement)
- Headers spécifiques (Content-Type, X-API-Key)
- Validators Pydantic avec warnings de sécurité

**Logging & Monitoring**
- Logger de sécurité centralisé avec rotation (10MB, 5 backups)
- Types d'événements structurés:
  - `AUTH_FAILURE` - Tentatives d'authentification échouées
  - `PATH_TRAVERSAL_ATTEMPT` - Tentatives d'attaque par traversée
  - `FILE_UPLOAD_REJECTED` - Fichiers rejetés par validation
  - `RATE_LIMIT_EXCEEDED` - Dépassements de rate limit
- Logs d'erreurs avec UUID tracking
- Logs de requêtes avec IP et user agent

**IDs Cryptographiquement Sécurisés**
- Job IDs: `conv_<random>` (128-bit sécurité, non-énumérables)
- Batch IDs: `batch_<random>` (128-bit sécurité, non-énumérables)
- Utilisation de `secrets.token_urlsafe()` au lieu de UUID4

**Documentation**
- `RENDER_DEPLOYMENT.md` - Guide complet de déploiement sécurisé
- `SWAGGER_UI_GUIDE.md` - Guide d'utilisation Swagger UI avec auth
- `TEST_RESULTS.md` - Résultats des tests de sécurité (16/16 passés)
- `.env.example` - Documentation complète des variables de sécurité
- Configuration `render.yaml` avec variables de sécurité

#### Modifié

**Configuration**
- `API_REQUIRE_AUTHENTICATION` par défaut à `true`
- `API_CORS_ORIGINS` par défaut à `[]` (vide)
- `API_CORS_ALLOW_CREDENTIALS` par défaut à `false`
- `API_RATE_LIMIT_ENABLED` par défaut à `true`
- Ajout de validators Pydantic pour configuration sécurité

**Gestion d'Erreurs**
- Messages d'erreur sanitisés en production
- Format de réponse standard FastAPI (`detail` au lieu de `error`)
- Gestion d'exceptions globale avec error_id UUID
- Logs d'erreurs sans exposition de données sensibles
- Handler spécifique pour RateLimitExceeded

**Tests**
- 16 nouveaux tests de sécurité automatisés (100% passés)
- Tests API adaptés à l'authentification (26/26 passés)
- Test fixtures avec génération automatique de clés
- Désactivation rate limiting pendant les tests
- Validation de tous les security fixes

**CI/CD**
- Résolution des erreurs de linting (10 imports inutilisés supprimés)
- Tests automatiques avec authentification
- Build Docker automatique vers GHCR
- Déploiement automatique sur Render

#### Corrigé

**Vulnérabilités Critiques**
- Path traversal dans `/api/v1/files/{file_id}/xml` - CORRIGÉ
- Absence d'authentification sur tous les endpoints - CORRIGÉ
- CORS ouvert à tous (`["*"]`) - CORRIGÉ
- Aucune validation de taille de fichier - CORRIGÉ

**Vulnérabilités Hautes**
- Rate limiting absent - CORRIGÉ
- Job IDs prévisibles (UUID4 truncated) - CORRIGÉ
- Messages d'erreur verbeux exposant détails internes - CORRIGÉ
- Path traversal dans storage service - CORRIGÉ
- Sanitisation fichiers insuffisante - CORRIGÉ

**Vulnérabilités Moyennes**
- Logging de sécurité absent - CORRIGÉ
- Validation magic number PDF manquante - CORRIGÉ
- Noms de fichiers non sanitisés - CORRIGÉ
- Configuration CORS non validée - CORRIGÉ

**Code Quality**
- 10 imports inutilisés supprimés (Ruff F401)
- Format de réponse d'erreur standardisé
- Tests API compatibles avec authentification

#### Score de Sécurité

- **Avant**: 7.2/10 (Risque Élevé) - 19 vulnérabilités
- **Après**: 3.1/10 (Risque Faible) - 0 vulnérabilités critiques/hautes
- **Score Production**: 9.1/10 ✅
- **Amélioration**: 57% de réduction du risque

#### Breaking Changes ⚠️

**Authentification Obligatoire**
- Tous les endpoints de conversion/batch nécessitent maintenant `X-API-Key` header
- Endpoints publics: `/`, `/api/v1/health`, `/docs`, `/redoc`, `/openapi.json`
- Migration: Générer clé API et l'ajouter à tous les clients

**CORS Restrictif**
- Par défaut: aucune origine autorisée
- Migration: Configurer `API_CORS_ORIGINS` avec domaines frontend spécifiques

**Configuration**
- Variables d'environnement de sécurité ajoutées (voir `.env.example`)
- `API_KEYS` obligatoire si `API_REQUIRE_AUTHENTICATION=true`

#### Migration Guide

**1. Générer Clé API**
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

**2. Configurer Environnement**

**Local** (`.env`):
```bash
API_KEYS="votre_cle_generee"
API_REQUIRE_AUTHENTICATION=true
API_RATE_LIMIT_ENABLED=true
```

**Render** (Dashboard):
- Aller dans Environment Variables
- Ajouter `API_KEYS` (SECRET)
- Autres variables déjà dans `render.yaml`

**3. Mettre à Jour Clients**
```python
# Ajouter header X-API-Key
headers = {"X-API-Key": "votre_cle"}
response = requests.post(url, headers=headers, files=files)
```

**4. Configurer CORS (si frontend)**
```bash
API_CORS_ORIGINS='["https://votre-frontend.com"]'
```

#### Ressources

- **Guide Déploiement**: `RENDER_DEPLOYMENT.md`
- **Guide Swagger UI**: `SWAGGER_UI_GUIDE.md`
- **Résultats Tests**: `TEST_RESULTS.md`
- **Configuration**: `.env.example`

---

## [1.0.0] - 2025-10-16

### Version Initiale

#### Ajouté

**API REST FastAPI**
- Conversion synchrone PDF → XML (`POST /api/v1/convert`)
- Conversion asynchrone avec job tracking (`POST /api/v1/convert/async`)
- Batch processing multi-fichiers (`POST /api/v1/batch`)
- Téléchargement de résultats (`GET /api/v1/convert/{job_id}/download`)
- Health check endpoint (`GET /api/v1/health`)
- Documentation Swagger UI (`/docs`) et ReDoc (`/redoc`)

**Conversion PDF RFCV → XML ASYCUDA**
- Extraction PDF avec pdfplumber
- Parsing de structures RFCV complexes
- Génération XML conforme ASYCUDA
- Support de 15+ structures de données
- Métriques de qualité de conversion

**Batch Processing**
- Traitement parallèle avec multiprocessing
- Configuration workers (1-8)
- Rapports de batch (JSON, CSV, Markdown)
- Métriques agrégées

**Infrastructure**
- Configuration Pydantic avec variables d'environnement
- Gestion de jobs en mémoire
- Nettoyage périodique des fichiers expirés
- Support Docker multi-stage
- Déploiement Render automatisé

**Documentation**
- README avec guide d'installation
- Documentation API complète
- Exemples d'utilisation cURL/Python
- Guide de déploiement Docker

#### Notes

Version initiale fonctionnelle mais **non sécurisée pour production**.
Mise à niveau vers v1.1.0 recommandée pour déploiements production.

---

## Types de Changements

- **Ajouté** - Nouvelles fonctionnalités
- **Modifié** - Changements dans les fonctionnalités existantes
- **Déprécié** - Fonctionnalités bientôt supprimées
- **Supprimé** - Fonctionnalités supprimées
- **Corrigé** - Corrections de bugs
- **Sécurité** - Corrections de vulnérabilités

[1.1.0]: https://github.com/kkzakaria/pdf-xml-asycuda/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/kkzakaria/pdf-xml-asycuda/releases/tag/v1.0.0
