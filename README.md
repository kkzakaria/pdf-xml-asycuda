# Convertisseur PDF RFCV → XML ASYCUDA

Outil d'automatisation pour la conversion des Rapports Finaux de Contrôle et de Vérification (RFCV) PDF vers le format XML ASYCUDA, éliminant la saisie manuelle dans le système douanier.

## 📋 Description

Ce convertisseur automatise l'extraction de données structurées depuis les documents PDF RFCV et génère des fichiers XML compatibles avec le système ASYCUDA (Automated System for Customs Data) utilisé en Côte d'Ivoire pour les opérations d'import/export.

## ✨ Fonctionnalités

- ✅ **Extraction automatique** des données RFCV depuis PDF
- ✅ **Génération XML ASYCUDA** conforme au schéma officiel
- ✅ **Validation complète** des données extraites
- ✅ **Système de métriques** pour évaluer la qualité de conversion
- ✅ **Tests automatisés** avec rapports détaillés
- ✅ **Support batch** pour traitement de masse

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
python converter.py input.pdf -o output.xml
```

### Conversion batch

```bash
python converter.py --batch input_directory/ -o output_directory/
```

### Mode verbeux

```bash
python converter.py input.pdf -v
```

### Exécuter les tests

```bash
python tests/test_converter.py -d tests/ -v
```

## 📁 Structure du projet

```
pdf-xml-asycuda/
├── src/
│   ├── models.py           # Modèles de données (15+ dataclasses)
│   ├── pdf_extractor.py    # Extraction PDF avec pdfplumber
│   ├── rfcv_parser.py      # Parsing des données RFCV
│   ├── xml_generator.py    # Génération XML ASYCUDA
│   └── metrics.py          # Système de métriques
├── tests/
│   └── test_converter.py   # Tests automatisés
├── scripts/
│   └── generate_report.py  # Générateur de rapports
├── converter.py            # CLI principal
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

- **pdfplumber** : Extraction de texte et tables depuis PDF
- **pandas** : Traitement des données tabulaires
- **xml.etree.ElementTree** : Génération XML
- **dataclasses** : Modélisation des données
- **regex** : Parsing avancé avec patterns Unicode

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
