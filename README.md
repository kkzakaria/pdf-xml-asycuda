# Convertisseur PDF RFCV → XML ASYCUDA

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

## 💻 Utilisation

### Conversion d'un seul fichier

```bash
# Conversion simple
python converter.py input.pdf

# Avec fichier de sortie personnalisé
python converter.py input.pdf -o output/custom.xml

# Mode verbeux
python converter.py input.pdf -v
```

### Traitement par lot (Batch)

Le système supporte plusieurs modes de traitement par lot :

#### Mode batch simple (fichiers multiples)

```bash
# Traiter plusieurs fichiers spécifiés
python converter.py file1.pdf file2.pdf file3.pdf --batch

# Avec pattern shell
python converter.py tests/*.pdf --batch
```

#### Mode batch avec dossier

```bash
# Traiter tous les PDFs d'un dossier
python converter.py -d tests/ --batch

# Recherche récursive dans sous-dossiers
python converter.py -d pdfs/ --recursive --batch

# Avec pattern de filtrage
python converter.py -d tests/ --pattern "RFCV*.pdf" --batch
```

#### Traitement parallèle

```bash
# Traiter avec 4 workers (plus rapide)
python converter.py -d tests/ --batch --workers 4

# Optimisation automatique selon CPU
python converter.py -d tests/ --batch --workers 8
```

#### Génération de rapports batch

```bash
# Rapport complet (JSON + CSV + Markdown)
python converter.py -d tests/ --batch --report batch_report

# Rapport JSON uniquement
python converter.py -d tests/ --batch --report results.json

# Rapport CSV uniquement
python converter.py -d tests/ --batch --report results.csv

# Rapport Markdown uniquement
python converter.py -d tests/ --batch --report results.md
```

#### Options avancées

```bash
# Dossier de sortie personnalisé
python converter.py -d tests/ --batch -o output/batch_results/

# Sans barre de progression
python converter.py -d tests/ --batch --no-progress

# Combinaison complète
python converter.py -d pdfs/ --recursive --pattern "*.pdf" \
  --batch --workers 4 --report full_report -o output/
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
│   ├── batch_processor.py   # 🆕 Traitement par lot parallèle
│   └── batch_report.py      # 🆕 Génération rapports batch
├── tests/
│   └── test_converter.py    # Tests automatisés
├── scripts/
│   └── generate_report.py   # Générateur de rapports
├── converter.py             # CLI principal (batch-enabled)
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
