# Guide d'Utilisation - Convertisseur PDF RFCV → XML ASYCUDA

## Description

Ce convertisseur automatise la transformation des fichiers PDF RFCV (Rapport Final de Contrôle et de Vérification) en format XML ASYCUDA, éliminant ainsi la nécessité de saisie manuelle dans le système douanier.

## Installation

```bash
# Installer les dépendances
pip install -r requirements.txt
```

## Utilisation

### Convertir un seul fichier

```bash
python converter.py "DOSSIER 18236.pdf"
```

Le fichier XML sera généré dans `output/DOSSIER 18236.xml`

### Convertir avec chemin de sortie personnalisé

```bash
python converter.py "DOSSIER 18236.pdf" -o chemin/personnalisé/sortie.xml
```

### Convertir avec mode verbeux (détails)

```bash
python converter.py "DOSSIER 18236.pdf" -v
```

Affiche :
- Nom de l'importateur et exportateur extraits
- Nombre d'articles et conteneurs
- Valeur CIF totale
- Étapes de traitement détaillées

### Convertir plusieurs fichiers (mode batch)

```bash
python converter.py *.pdf --batch
```

ou

```bash
python converter.py "DOSSIER 17745.pdf" "DOSSIER 18236.pdf" "DOSSIER 18237.pdf" --batch
```

## Structure du Projet

```
pdf-xml-asycuda/
├── config/              # Fichiers de configuration (mapping)
├── src/                 # Code source
│   ├── models.py           # Modèles de données
│   ├── pdf_extractor.py    # Extraction PDF avec pdfplumber
│   ├── rfcv_parser.py      # Parsing structure RFCV
│   └── xml_generator.py    # Génération XML ASYCUDA
├── tests/               # Tests unitaires
├── output/              # Fichiers XML générés
├── converter.py         # Script CLI principal
├── requirements.txt     # Dépendances Python
└── README.md           # Documentation
```

## Données Extraites

Le convertisseur extrait et mappe automatiquement :

### Informations Générales
- Numéro RFCV
- Date du document
- Nombre de pages/formulaires
- Type de déclaration (Import/Export)

### Traders (Opérateurs)
- **Exportateur** : Nom, adresse, code
- **Importateur** : Nom, adresse, code destinataire
- **Déclarant** : Informations du déclarant en douane

### Transport
- Mode de transport (maritime, aérien, routier)
- Nom du navire/transporteur
- Lieux de chargement et déchargement
- Informations conteneurs
- INCOTERMS (CFR, FOB, CIF, etc.)

### Informations Financières
- Valeur FOB (Free On Board)
- Fret
- Assurance
- Valeur CIF (Cost Insurance Freight)
- Devise et taux de change
- Mode de paiement

### Articles/Marchandises
- Description des marchandises
- Code tarifaire HS (Harmonized System)
- Quantité et unités
- Poids net et brut
- Valeur unitaire et totale
- Pays d'origine

### Conteneurs
- Numéro de conteneur
- Type (20', 40', 40' HC, etc.)
- Poids et nombre de colis

## Format de Sortie

Le XML généré respecte strictement le format ASYCUDA avec :
- Structure hiérarchique complète
- Éléments `<null/>` pour champs vides (conformité ASYCUDA)
- Encodage UTF-8
- Indentation pour lisibilité

## Exemples de Résultats

```
Conversion de: DOSSIER 18236.pdf
Sortie vers: output/DOSSIER 18236.xml
------------------------------------------------------------
Étape 1/2: Extraction et parsing du PDF...
  ✓ Extraction réussie
  - Importateur: BOUAKE COMMERCE SARL
  - Exportateur: KOLOKELH TRADING FZE
  - Nombre d'articles: 75
  - Nombre de conteneurs: 5
  - Valeur CIF totale: 46037.70

Étape 2/2: Génération du XML ASYCUDA...
  ✓ Génération XML réussie
------------------------------------------------------------
✓ Conversion terminée avec succès!
  Fichier XML généré: output/DOSSIER 18236.xml
```

## Importation dans ASYCUDA

Une fois le XML généré :

1. Ouvrir le système ASYCUDA
2. Aller dans **Import/Export** > **Importer déclaration**
3. Sélectionner le fichier XML généré
4. Vérifier les données importées
5. Valider et soumettre la déclaration

## Personnalisation

### Ajuster les Patterns d'Extraction

Modifier `src/rfcv_parser.py` pour adapter les regex si le format RFCV change :

```python
# Exemple : extraire numéro RFCV
ident.manifest_reference = self._extract_field(r'No\.\s*RFCV[:\s]+(\S+)')
```

### Modifier le Mapping XML

Le mapping vers les éléments XML ASYCUDA se trouve dans `src/xml_generator.py`.

## Limitations Connues

1. **Extraction Traders** : Certains noms d'importateur/exportateur peuvent nécessiter un ajustement des regex
2. **Items complexes** : Les articles avec descriptions très longues peuvent nécessiter un nettoyage manuel
3. **Taxation** : Les lignes de taxation sont générées vides (à compléter manuellement dans ASYCUDA si nécessaire)

## Dépannage

### Erreur "Module not found"
```bash
pip install -r requirements.txt
```

### Fichier PDF corrompu
Vérifier que le PDF s'ouvre correctement dans un lecteur PDF standard.

### XML malformé
Utiliser un validateur XML en ligne pour identifier les erreurs de structure.

### Données manquantes dans le XML
Activer le mode verbeux (`-v`) pour voir quelles données sont extraites :
```bash
python converter.py "fichier.pdf" -v
```

## Support et Améliorations

Pour signaler des problèmes ou suggérer des améliorations :
1. Vérifier la structure du PDF source
2. Tester avec le mode verbeux
3. Consulter les logs d'extraction
4. Ajuster les patterns regex si nécessaire

## Bibliothèques Utilisées

- **pdfplumber** 0.10.0+ : Extraction robuste de texte et tables depuis PDF
- **pandas** 2.0.0+ : Manipulation de données tabulaires
- **xml.etree.ElementTree** : Génération XML (bibliothèque standard Python)
- **python-dateutil** 2.8.0+ : Gestion des dates

## Licence

Ce projet est développé pour automatiser le traitement douanier et réduire les erreurs de saisie manuelle.
