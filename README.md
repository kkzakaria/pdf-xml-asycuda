# Convertisseur PDF RFCV → XML ASYCUDA

[![Tests](https://github.com/kkzakaria/pdf-xml-asycuda/actions/workflows/test.yml/badge.svg)](https://github.com/kkzakaria/pdf-xml-asycuda/actions/workflows/test.yml)
[![Docker Build](https://github.com/kkzakaria/pdf-xml-asycuda/actions/workflows/docker.yml/badge.svg)](https://github.com/kkzakaria/pdf-xml-asycuda/actions/workflows/docker.yml)
[![Release](https://github.com/kkzakaria/pdf-xml-asycuda/actions/workflows/release.yml/badge.svg)](https://github.com/kkzakaria/pdf-xml-asycuda/actions/workflows/release.yml)
[![Docker Image](https://ghcr-badge.egpl.dev/kkzakaria/pdf-xml-asycuda/latest_tag?trim=major&label=Docker)](https://github.com/kkzakaria/pdf-xml-asycuda/pkgs/container/pdf-xml-asycuda)

Outil d'automatisation pour la conversion des Rapports Finaux de Contrôle et de Vérification (RFCV) PDF vers le format XML ASYCUDA, éliminant la saisie manuelle dans le système douanier.

## 📋 Description

Ce convertisseur automatise l'extraction de données structurées depuis les documents PDF RFCV et génère des fichiers XML compatibles avec le système ASYCUDA (Automated System for Customs Data) utilisé en Côte d'Ivoire pour les opérations d'import/export.

## ✨ Fonctionnalités

### Extraction et Conversion
- ✅ **Extraction automatique** des données RFCV depuis PDF
- ✅ **Génération XML ASYCUDA** conforme au schéma officiel
- ✅ **Validation complète** des données extraites
- ✅ **Système de métriques** pour évaluer la qualité de conversion
- ✅ **Tests automatisés** avec rapports détaillés

### Traitement par Lot
- ✅ **Batch processing** avec support dossiers et recherche récursive
- ✅ **Traitement parallèle** avec multiprocessing (jusqu'à N workers)
- ✅ **Filtrage par patterns** pour sélectionner des fichiers spécifiques
- ✅ **Barre de progression** avec tqdm pour visualiser l'avancement
- ✅ **Rapports batch** en JSON, CSV et Markdown
- ✅ **Gestion d'erreurs robuste** avec continuation automatique

### API REST
- ✅ **13 endpoints REST** pour intégration complète
- ✅ **Conversion synchrone et asynchrone** avec job tracking
- ✅ **Batch processing API** avec suivi de progression
- ✅ **Upload multipart** avec validation
- ✅ **Background tasks** pour conversions longues
- ✅ **Métriques et monitoring** en temps réel
- ✅ **Documentation OpenAPI/Swagger** interactive
- ✅ **CORS configuré** pour intégration web

## 📊 Résultats

- **Taux de réussite** : 100% (7/7 PDFs testés)
- **Taux de remplissage** : 68.5% en moyenne
- **Performance** : ~636ms par conversion
- **Warnings** : 0

## 🚀 Installation

### Prérequis

- Python 3.8+
- pip

### Installation des dépendances

```bash
pip install -r requirements.txt
```

## 🌐 Déploiement Production

### Déploiement sur Render (Recommandé)

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)

Le projet est configuré pour un déploiement automatique sur Render :

1. **Connectez-vous à Render** avec votre compte GitHub
2. **Créez un Blueprint** depuis le repository
3. Render détectera automatiquement `render.yaml` et déploiera l'application

#### Configuration Rapide

```bash
# 1. Connectez votre repository GitHub à Render
# 2. Render créera automatiquement le service depuis render.yaml
# 3. Votre API sera disponible sur: https://votre-app.onrender.com
```

#### Déploiement Automatique

- ✅ Déploiement automatique à chaque push sur `main`
- ✅ Déploiement automatique à chaque nouvelle release (`v*.*.*`)
- ✅ Images Docker récupérées depuis `ghcr.io`
- ✅ SSL/HTTPS automatique
- ✅ Health checks configurés

#### Plans Disponibles

- **Free** : Gratuit, parfait pour débuter (mise en veille après 15min d'inactivité)
- **Starter** : $7/mois, sans mise en veille, stockage persistant
- **Standard** : $25/mois, 2GB RAM, scaling horizontal

📖 **Documentation complète** : [README_DEPLOY.md](README_DEPLOY.md)

### Autres Options de Déploiement

- **Railway** : Déploiement Docker simple
- **Fly.io** : Excellent pour latence globale
- **DigitalOcean App Platform** : Stable et abordable
- **AWS ECS/Fargate** : Production enterprise

### Docker (Auto-hébergé)

```bash
# Utiliser l'image publiée
docker pull ghcr.io/kkzakaria/pdf-xml-asycuda:latest
docker run -p 8000:8000 ghcr.io/kkzakaria/pdf-xml-asycuda:latest

# Ou avec docker-compose
docker-compose up -d
```

## 💻 Utilisation

### API REST (Mode Service)

Le convertisseur inclut une API REST complète pour l'intégration dans vos applications.

#### Démarrage de l'API

```bash
# Installation des dépendances API
pip install -r requirements.txt

# Démarrer le serveur API
python run_api.py

# Ou avec uvicorn directement
python3 -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

L'API sera disponible sur `http://localhost:8000`
- Documentation interactive: `http://localhost:8000/docs`
- Documentation alternative: `http://localhost:8000/redoc`

#### Endpoints API

**Conversion**
- `POST /api/v1/convert` - Conversion synchrone (upload PDF → retourne XML immédiatement)
- `POST /api/v1/convert/async` - Conversion asynchrone (retourne job_id)
- `GET /api/v1/convert/{job_id}` - Status d'un job de conversion
- `GET /api/v1/convert/{job_id}/result` - Résultat complet avec métriques
- `GET /api/v1/convert/{job_id}/download` - Télécharger le XML généré

**Batch Processing**
- `POST /api/v1/batch` - Conversion batch de plusieurs PDFs
- `GET /api/v1/batch/{batch_id}/status` - Status du batch
- `GET /api/v1/batch/{batch_id}/results` - Résultats détaillés
- `GET /api/v1/batch/{batch_id}/report` - Rapport complet (JSON)

**Fichiers**
- `GET /api/v1/files/{file_id}/xml` - Télécharger un XML par ID
- `GET /api/v1/files/{file_id}/metadata` - Métadonnées du fichier

**Monitoring**
- `GET /api/v1/health` - Health check de l'API
- `GET /api/v1/metrics` - Métriques système globales
- `GET /api/v1/metrics/{job_id}` - Métriques d'un job spécifique

#### Exemples d'utilisation de l'API

**⚠️ Important**: Le paramètre `taux_douane` (taux de change douanier) est **obligatoire** pour toutes les conversions. Ce taux est communiqué par la douane avant chaque conversion.

**Conversion simple avec curl:**
```bash
# Upload et conversion synchrone (taux_douane requis)
curl -X POST "http://localhost:8000/api/v1/convert" \
  -F "file=@DOSSIER_18236.pdf" \
  -F "taux_douane=573.1390"

# Conversion asynchrone
curl -X POST "http://localhost:8000/api/v1/convert/async" \
  -F "file=@DOSSIER_18236.pdf" \
  -F "taux_douane=573.1390"

# Vérifier le status
curl "http://localhost:8000/api/v1/convert/{job_id}"

# Télécharger le XML
curl -O "http://localhost:8000/api/v1/convert/{job_id}/download"
```

**Batch processing:**
```bash
# Upload multiple PDFs avec taux individuels (format JSON)
curl -X POST "http://localhost:8000/api/v1/batch" \
  -F "files=@file1.pdf" \
  -F "files=@file2.pdf" \
  -F "files=@file3.pdf" \
  -F "workers=4" \
  -F "taux_douanes=[573.1390, 573.1390, 573.1390]"

# Status du batch
curl "http://localhost:8000/api/v1/batch/{batch_id}/status"

# Rapport détaillé
curl "http://localhost:8000/api/v1/batch/{batch_id}/report"
```

**Exemple Python avec requests:**
```python
import requests
import json

# Conversion synchrone (taux_douane requis)
with open('DOSSIER_18236.pdf', 'rb') as f:
    response = requests.post(
        'http://localhost:8000/api/v1/convert',
        files={'file': f},
        data={'taux_douane': 573.1390}  # Taux douanier obligatoire
    )
    result = response.json()
    print(f"Conversion: {result['success']}")
    print(f"Output: {result['output_file']}")
    print(f"Métriques: {result['metrics']}")

# Batch conversion avec taux individuels
files = [
    ('files', open('file1.pdf', 'rb')),
    ('files', open('file2.pdf', 'rb')),
    ('files', open('file3.pdf', 'rb'))
]
# Taux pour chaque fichier (même ordre que les fichiers)
taux_list = [573.1390, 573.1390, 573.1390]

response = requests.post(
    'http://localhost:8000/api/v1/batch',
    files=files,
    data={
        'workers': 4,
        'taux_douanes': json.dumps(taux_list)  # Liste JSON de taux
    }
)
batch = response.json()
batch_id = batch['batch_id']

# Suivre la progression
import time
while True:
    status = requests.get(f'http://localhost:8000/api/v1/batch/{batch_id}/status').json()
    print(f"Progression: {status['processed']}/{status['total_files']}")
    if status['status'] == 'completed':
        break
    time.sleep(1)
```

#### Configuration API

Créer un fichier `.env` pour personnaliser la configuration:
```bash
cp .env.example .env
```

Variables disponibles:
- `API_HOST` - Hôte du serveur (défaut: 0.0.0.0)
- `API_PORT` - Port du serveur (défaut: 8000)
- `API_DEBUG` - Mode debug (défaut: False)
- `API_UPLOAD_DIR` - Dossier uploads (défaut: uploads)
- `API_OUTPUT_DIR` - Dossier outputs (défaut: output)
- `API_MAX_UPLOAD_SIZE` - Taille max upload en octets (défaut: 50MB)
- `API_DEFAULT_WORKERS` - Workers par défaut (défaut: 4)
- `API_MAX_WORKERS` - Workers maximum (défaut: 8)
- `API_JOB_EXPIRY_HOURS` - Expiration des jobs (défaut: 24h)

### CLI - Conversion d'un seul fichier

**⚠️ Important**: Le paramètre `--taux-douane` (taux de change douanier) est **obligatoire** pour toutes les conversions.

```bash
# Conversion simple avec taux douanier obligatoire
python converter.py input.pdf --taux-douane 573.1390

# Avec fichier de sortie personnalisé
python converter.py input.pdf --taux-douane 573.1390 -o output/custom.xml

# Mode verbeux
python converter.py input.pdf --taux-douane 573.1390 -v
```

### Traitement par lot (Batch)

Le système supporte plusieurs modes de traitement par lot :

#### Mode batch simple (fichiers multiples)

```bash
# Traiter plusieurs fichiers spécifiés avec même taux
python converter.py file1.pdf file2.pdf file3.pdf --batch --taux-douane 573.1390

# Avec pattern shell
python converter.py tests/*.pdf --batch --taux-douane 573.1390
```

#### Mode batch avec dossier

```bash
# Traiter tous les PDFs d'un dossier avec même taux
python converter.py -d tests/ --batch --taux-douane 573.1390

# Recherche récursive dans sous-dossiers
python converter.py -d pdfs/ --recursive --batch --taux-douane 573.1390

# Avec pattern de filtrage
python converter.py -d tests/ --pattern "RFCV*.pdf" --batch --taux-douane 573.1390
```

#### Traitement parallèle

```bash
# Traiter avec 4 workers (plus rapide)
python converter.py -d tests/ --batch --workers 4 --taux-douane 573.1390

# Optimisation automatique selon CPU
python converter.py -d tests/ --batch --workers 8 --taux-douane 573.1390
```

#### Génération de rapports batch

```bash
# Rapport complet (JSON + CSV + Markdown)
python converter.py -d tests/ --batch --report batch_report --taux-douane 573.1390

# Rapport JSON uniquement
python converter.py -d tests/ --batch --report results.json --taux-douane 573.1390

# Rapport CSV uniquement
python converter.py -d tests/ --batch --report results.csv --taux-douane 573.1390

# Rapport Markdown uniquement
python converter.py -d tests/ --batch --report results.md --taux-douane 573.1390
```

#### Options avancées

```bash
# Dossier de sortie personnalisé
python converter.py -d tests/ --batch -o output/batch_results/ --taux-douane 573.1390

# Sans barre de progression
python converter.py -d tests/ --batch --no-progress --taux-douane 573.1390

# Combinaison complète
python converter.py -d pdfs/ --recursive --pattern "*.pdf" \
  --batch --workers 4 --report full_report -o output/ --taux-douane 573.1390
```

### Performance batch

Le traitement par lot offre des gains de performance significatifs :

| Mode | Fichiers | Temps | Performance |
|------|----------|-------|-------------|
| Séquentiel | 7 PDFs | 3.64s | 0.52s/fichier |
| Parallèle (4 workers) | 7 PDFs | 2.40s | 0.34s/fichier |
| **Gain** | - | **-34%** | **-35%** |

### Exécuter les tests

```bash
# Tests complets avec rapport
python tests/test_converter.py -d tests/ -v

# Tests rapides
python tests/test_converter.py -d tests/
```

## 📁 Structure du projet

```
pdf-xml-asycuda/
├── src/
│   ├── models.py            # Modèles de données (15+ dataclasses)
│   ├── pdf_extractor.py     # Extraction PDF avec pdfplumber
│   ├── rfcv_parser.py       # Parsing des données RFCV
│   ├── xml_generator.py     # Génération XML ASYCUDA
│   ├── metrics.py           # Système de métriques
│   ├── batch_processor.py   # Traitement par lot parallèle
│   ├── batch_report.py      # Génération rapports batch
│   └── api/                 # 🆕 API REST FastAPI
│       ├── main.py          # Application FastAPI
│       ├── core/            # Configuration et dépendances
│       ├── models/          # Modèles Pydantic (requests/responses)
│       ├── routes/          # Endpoints API (convert, batch, files, health)
│       ├── services/        # Services métier (wrappers)
│       └── utils/           # Utilitaires
├── tests/
│   └── test_converter.py    # Tests automatisés
├── scripts/
│   └── generate_report.py   # Générateur de rapports
├── converter.py             # CLI principal (batch-enabled)
├── run_api.py              # 🆕 Script de démarrage API
├── .env.example            # 🆕 Exemple configuration API
└── requirements.txt
```

## 🔍 Données extraites

### Sections principales

- **Identification** : Numéro RFCV, type de déclaration, bureau de douane
- **Traders** : Exportateur, Importateur/Consignataire
- **Transport** : Mode, navire, INCOTERM, lieux de chargement/déchargement
- **Financial** : Mode de paiement, codes de transaction
- **Valuation** : Valeurs FOB, CIF, fret, assurance, devises
- **Items** : Articles avec codes SH, quantités, valeurs
- **Containers** : Liste des conteneurs avec types et identifiants

## 💰 Calcul de l'Assurance

Le système calcule automatiquement l'assurance (section 21) selon la formule douanière officielle.

### Formule de calcul

```
Assurance XOF = 2500 + (FOB + FRET) × TAUX × 0.15%
```

**Composantes :**
- **2500** : Montant fixe en XOF (Franc CFA)
- **FOB** : Total Valeur FOB attestée (section 19)
- **FRET** : Fret Attesté (section 20)
- **TAUX** : Taux de change douanier (variable, communiqué par la douane)
- **0.15%** : Taux d'assurance (0.0015)

### Caractéristiques

- ✅ **Devise** : Toujours en XOF (Franc CFA) avec taux 1.0
- ✅ **Répartition proportionnelle** : Distribution automatique sur les articles selon leur FOB
- ✅ **Gestion des valeurs nulles** : Si FOB ou FRET manquant, assurance = null
- ✅ **Taux obligatoire** : Le paramètre `taux_douane` est requis pour toutes les conversions

### Exemple de calcul

**Données :**
- FOB : 10,220 USD
- FRET : 2,000 USD
- TAUX : 573.139 (USD)

**Calcul :**
```
Assurance = 2500 + (10220 + 2000) × 573.139 × 0.0015
         = 2500 + 12220 × 573.139 × 0.0015
         = 2500 + 10505.64
         = 13005.64 XOF
```

**Répartition :**
L'assurance totale est ensuite répartie proportionnellement sur les articles selon leur FOB respectif, avec application de la méthode du reste le plus grand (Largest Remainder Method) pour garantir que la somme des articles égale exactement le total.

## 🛠️ Technologies

### Extraction et Parsing
- **pdfplumber** : Extraction de texte et tables depuis PDF
- **pandas** : Traitement des données tabulaires
- **regex** : Parsing avancé avec patterns Unicode
- **dataclasses** : Modélisation des données

### Génération et Validation
- **xml.etree.ElementTree** : Génération XML
- **Système de métriques** : Validation et qualité

### Traitement par Lot
- **multiprocessing** : Traitement parallèle
- **tqdm** : Barres de progression interactives
- **concurrent.futures** : Gestion asynchrone des workers
- **JSON/CSV** : Export des rapports batch

### API REST
- **FastAPI** : Framework API moderne et performant
- **Uvicorn** : Serveur ASGI haute performance
- **Pydantic v2** : Validation de données et sérialisation
- **python-multipart** : Support des uploads multipart
- **aiofiles** : Opérations fichiers asynchrones
- **Background tasks** : Conversions asynchrones
- **OpenAPI/Swagger** : Documentation interactive automatique

## 📈 Métriques de qualité

Le système inclut un collecteur de métriques détaillé :

- Taux de remplissage des champs (0-100%)
- Temps d'extraction et génération
- Validation XML
- Détection de warnings
- Complétude des données par section

## 🤝 Contribution

Les contributions sont les bienvenues ! N'hésitez pas à :

1. Fork le projet
2. Créer une branche feature (`git checkout -b feature/AmazingFeature`)
3. Commit vos changements (`git commit -m 'Add AmazingFeature'`)
4. Push vers la branche (`git push origin feature/AmazingFeature`)
5. Ouvrir une Pull Request

## 📝 Notes techniques

### Gestion des apostrophes Unicode

Le système gère correctement les deux types d'apostrophes :
- Apostrophe ASCII standard (`'`)
- Apostrophe Unicode U+2019 (`'`)

Ceci est crucial pour l'extraction des noms d'exportateurs et importateurs.

### Format XML ASYCUDA

Le XML généré utilise la convention `<null/>` pour les champs vides, conformément au schéma ASYCUDA standard.

## 📄 Licence

Ce projet est sous licence MIT.

## 👨‍💻 Auteur

Développé pour automatiser le processus douanier en Côte d'Ivoire.

## 🔗 Liens utiles

- [Documentation ASYCUDA](https://asycuda.org/)
- [pdfplumber Documentation](https://github.com/jsvine/pdfplumber)
