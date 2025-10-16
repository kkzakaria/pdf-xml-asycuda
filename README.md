# Convertisseur PDF RFCV → XML ASYCUDA

Convertit automatiquement les fichiers PDF RFCV (Rapport Final de Contrôle et de Vérification) en format XML ASYCUDA pour éviter la saisie manuelle dans le système douanier.

## 🚀 Démarrage Rapide

```bash
# Installation
pip install -r requirements.txt

# Conversion simple
python converter.py "DOSSIER 18236.pdf"

# Conversion avec détails
python converter.py "DOSSIER 18236.pdf" -v

# Conversion multiple (batch)
python converter.py *.pdf --batch
```

## ✨ Fonctionnalités

- ✅ Extraction automatique des données depuis PDF RFCV
- ✅ Génération XML conforme au format ASYCUDA
- ✅ Conversion batch de plusieurs fichiers
- ✅ Support des conteneurs et articles multiples
- ✅ Gestion des devises et taux de change
- ✅ Mode verbeux pour debugging
- ✅ Structure XML avec éléments `<null/>` pour conformité ASYCUDA

## 📊 Résultats

```txt
✓ 3/3 conversions réussies
- DOSSIER 17745.pdf → output/DOSSIER 17745.xml (1.6MB, 150+ articles)
- DOSSIER 18236.pdf → output/DOSSIER 18236.xml (663KB, 75 articles)
- DOSSIER 18237.pdf → output/DOSSIER 18237.xml (533KB, 60 articles)
```

## 📖 Documentation

Consultez [GUIDE_UTILISATION.md](GUIDE_UTILISATION.md) pour :

- Guide d'utilisation complet
- Exemples détaillés
- Personnalisation et dépannage
- Importation dans ASYCUDA

## 🏗️ Structure du Projet

```text
pdf-xml-asycuda/
├── src/
│   ├── models.py           # Modèles de données
│   ├── pdf_extractor.py    # Extraction PDF
│   ├── rfcv_parser.py      # Parsing RFCV
│   └── xml_generator.py    # Génération XML
├── output/                 # XMLs générés
├── converter.py            # Script principal
├── requirements.txt
├── README.md
└── GUIDE_UTILISATION.md
```

## 🛠️ Bibliothèques

- **pdfplumber** - Extraction de données depuis PDF
- **pandas** - Traitement des données tabulaires
- **xml.etree.ElementTree** - Génération XML

## 📝 Exemple de Sortie

```xml
<?xml version="1.0" encoding="utf-8"?>
<ASYCUDA>
  <Property>
    <Sad_flow>I</Sad_flow>
    <Total_number_of_items>75</Total_number_of_items>
    <Total_number_of_packages>3287</Total_number_of_packages>
  </Property>
  <Identification>
    <Customs_clearance_office_code>CIAB1</Customs_clearance_office_code>
    <Type_of_declaration>IM</Type_of_declaration>
  </Identification>
  <!-- ... sections Traders, Transport, Financial, Items ... -->
</ASYCUDA>
```

## 🎯 Cas d'Usage

- Déclarations d'importation/exportation
- Traitement douanier automatisé
- Réduction des erreurs de saisie manuelle
- Gain de temps significatif (minutes vs heures)

## ⚡ Performance

- Conversion PDF → XML : ~2-5 secondes par document
- Support de documents multi-pages
- Extraction de 100+ articles par document
