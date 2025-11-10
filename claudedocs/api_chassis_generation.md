# Documentation API - Génération de Châssis VIN

Guide complet pour utiliser la fonctionnalité de génération automatique de châssis VIN via l'API REST.

## Vue d'ensemble

L'API v2.1 supporte la génération automatique de numéros VIN ISO 3779 (17 caractères avec checksum) lors de la conversion RFCV → XML ASYCUDA.

### Caractéristiques

- **Format**: VIN ISO 3779 (17 caractères, pas de I/O/Q)
- **Unicité**: Persistance des séquences entre conversions
- **Personnalisation**: WMI, VDS, année, code usine configurables
- **Limitation**: Contrôle du nombre de VIN générés
- **Thread-safe**: Génération sécurisée en mode parallèle

## Configuration JSON

### Structure de base

```json
{
  "generate_chassis": true,
  "quantity": 180,
  "wmi": "LZS",
  "year": 2025,
  "vds": "HCKZS",
  "plant_code": "S",
  "ensure_unique": true
}
```

### Paramètres

| Paramètre | Type | Requis | Défaut | Description |
|-----------|------|--------|--------|-------------|
| `generate_chassis` | boolean | ✅ Oui | - | Active la génération automatique |
| `quantity` | integer | ✅ Oui | - | Nombre de VIN à générer (> 0) |
| `wmi` | string(3) | ✅ Oui | - | World Manufacturer Identifier (ex: LZS, LFV) |
| `year` | integer | ✅ Oui | - | Année fabrication (1980-2055) |
| `vds` | string(5) | ❌ Non | "HCKZS" | Vehicle Descriptor Section |
| `plant_code` | string(1) | ❌ Non | "S" | Code usine de fabrication |
| `ensure_unique` | boolean | ❌ Non | true | Garantir unicité via persistance |

### Exemples de configurations

**Configuration minimale** (180 châssis LZS/2025):
```json
{
  "generate_chassis": true,
  "quantity": 180,
  "wmi": "LZS",
  "year": 2025
}
```

**Configuration complète** (50 châssis LFV/2024):
```json
{
  "generate_chassis": true,
  "quantity": 50,
  "wmi": "LFV",
  "year": 2024,
  "vds": "BA01A",
  "plant_code": "S",
  "ensure_unique": true
}
```

## Endpoints API

### 1. Conversion Synchrone

**Endpoint**: `POST /api/v1/convert`

**Description**: Upload un PDF et retourne le XML immédiatement.

**Paramètres**:
- `file` (multipart): Fichier PDF RFCV (max 50MB)
- `taux_douane` (form): Taux douanier (ex: 573.139)
- `rapport_paiement` (form, optionnel): Numéro quittance Trésor
- `chassis_config` (form, optionnel): Configuration JSON (string)

**Exemple curl**:
```bash
curl -X POST "http://localhost:8000/api/v1/convert" \
  -H "X-API-Key: votre_cle_api" \
  -F "file=@DOSSIER_18236.pdf" \
  -F "taux_douane=573.139" \
  -F 'chassis_config={"generate_chassis":true,"quantity":180,"wmi":"LZS","year":2025}'
```

**Réponse** (200 OK):
```json
{
  "success": true,
  "job_id": "conv_abc123xyz",
  "filename": "DOSSIER_18236.pdf",
  "output_file": "DOSSIER_18236.xml",
  "message": "Conversion réussie",
  "metrics": {
    "items_count": 180,
    "containers_count": 0,
    "fill_rate": 72.5,
    "warnings_count": 0,
    "warnings": [],
    "xml_valid": true,
    "has_exporter": true,
    "has_consignee": true,
    "processing_time": 1.2
  },
  "processing_time": 1.2
}
```

### 2. Conversion Asynchrone

**Endpoint**: `POST /api/v1/convert/async`

**Description**: Upload un PDF et reçoit un `job_id` pour récupérer le résultat plus tard.

**Paramètres**: Identiques à la conversion synchrone

**Exemple curl**:
```bash
curl -X POST "http://localhost:8000/api/v1/convert/async" \
  -H "X-API-Key: votre_cle_api" \
  -F "file=@DOSSIER_18237.pdf" \
  -F "taux_douane=573.139" \
  -F 'chassis_config={"generate_chassis":true,"quantity":50,"wmi":"LFV","year":2024}'
```

**Réponse** (200 OK):
```json
{
  "job_id": "conv_def456uvw",
  "status": "pending",
  "message": "Conversion en cours",
  "created_at": "2025-01-10T14:30:00Z"
}
```

**Vérifier le statut**:
```bash
curl -X GET "http://localhost:8000/api/v1/convert/conv_def456uvw" \
  -H "X-API-Key: votre_cle_api"
```

**Télécharger le résultat**:
```bash
curl -X GET "http://localhost:8000/api/v1/convert/conv_def456uvw/download" \
  -H "X-API-Key: votre_cle_api" \
  -o DOSSIER_18237.xml
```

### 3. Conversion Batch

**Endpoint**: `POST /api/v1/batch`

**Description**: Upload plusieurs PDFs avec configuration individuelle par fichier.

**Paramètres**:
- `files[]` (multipart): Liste de fichiers PDF
- `taux_douanes` (form): Liste JSON de taux (ex: `[573.139, 580.25]`)
- `chassis_configs` (form, optionnel): Liste JSON de configs (ex: `[{...}, null, {...}]`)
- `workers` (form, optionnel): Nombre de workers (1-8, défaut: 4)

**Exemple curl** (3 fichiers avec configs différentes):
```bash
curl -X POST "http://localhost:8000/api/v1/batch" \
  -H "X-API-Key: votre_cle_api" \
  -F "files=@DOSSIER1.pdf" \
  -F "files=@DOSSIER2.pdf" \
  -F "files=@DOSSIER3.pdf" \
  -F 'taux_douanes=[573.139, 573.139, 580.25]' \
  -F 'chassis_configs=[
    {"generate_chassis":true,"quantity":180,"wmi":"LZS","year":2025},
    {"generate_chassis":true,"quantity":50,"wmi":"LFV","year":2024},
    null
  ]' \
  -F "workers=4"
```

**Interprétation**:
- **Fichier 1** (`DOSSIER1.pdf`): Génère 180 VIN (LZS/2025)
- **Fichier 2** (`DOSSIER2.pdf`): Génère 50 VIN (LFV/2024)
- **Fichier 3** (`DOSSIER3.pdf`): Détection automatique (pas de génération)

**Réponse** (200 OK):
```json
{
  "batch_id": "batch_xyz789abc",
  "status": "processing",
  "total_files": 3,
  "processed": 0,
  "successful": 0,
  "failed": 0,
  "created_at": "2025-01-10T14:35:00Z",
  "completed_at": null,
  "message": "Traitement en cours: 0/3 fichiers"
}
```

**Vérifier le statut batch**:
```bash
curl -X GET "http://localhost:8000/api/v1/batch/batch_xyz789abc/status" \
  -H "X-API-Key: votre_cle_api"
```

**Récupérer les résultats batch**:
```bash
curl -X GET "http://localhost:8000/api/v1/batch/batch_xyz789abc/results" \
  -H "X-API-Key: votre_cle_api"
```

## Format XML Généré

### Structure ASYCUDA

Pour chaque véhicule avec VIN généré, le XML contient:

```xml
<Item>
  <!-- Document châssis (code 6122) -->
  <Attached_documents>
    <Attached_document_code>6122</Attached_document_code>
    <Attached_document_name>CHASSIS MOTOS</Attached_document_name>
    <Attached_document_reference>LZSHCKZS0SS000001</Attached_document_reference>
    <Attached_document_from_rule>1</Attached_document_from_rule>
  </Attached_documents>

  <!-- Châssis dans Marks2 avec préfixe CH: -->
  <Packages>
    <Marks1_of_packages>TRICYCLE AP150ZK</Marks1_of_packages>
    <Marks2_of_packages>CH: LZSHCKZS0SS000001</Marks2_of_packages>
  </Packages>

  <!-- Description préservée (données originales intactes) -->
  <Goods_description>
    <Country_of_origin_code>CN</Country_of_origin_code>
    <Description_of_goods>TRICYCLE AP150ZK LZSHCKZS2S8054073</Description_of_goods>
  </Goods_description>

  <!-- Autres données RFCV (Code HS, FOB, etc.) -->
  <Tarification>
    <HScode>
      <Commodity_code>87042110</Commodity_code>
    </HScode>
    <Item_price>532.0</Item_price>
  </Tarification>
</Item>
```

### Séquence de VIN

**Format**: `WMI (3) + VDS (5) + Year (1) + Plant (1) + Checksum (1) + Sequence (6)`

**Exemple avec LZS/2025**:
- `LZSHCKZS0SS000001` → Premier VIN
- `LZSHCKZS2SS000002` → Deuxième VIN
- `LZSHCKZS4SS000003` → Troisième VIN
- ...
- `LZSHCKZS6SS000180` → 180ème VIN

**Code année ISO 3779**:
- 2024 → `R`
- 2025 → `S`
- 2026 → `T`

**Persistance**: Les séquences sont sauvegardées dans `data/chassis_sequences.json`:
```json
{
  "LZSHCKZSS": 240,
  "LFVHCKZSR": 75
}
```

## Gestion des erreurs

### Erreur 400 - Paramètres invalides

**Cas**: Champs requis manquants dans `chassis_config`

```json
{
  "error": "Champs requis manquants dans chassis_config: quantity, wmi"
}
```

**Solution**: Fournir tous les paramètres requis (`generate_chassis`, `quantity`, `wmi`, `year`)

### Erreur 400 - Format JSON invalide

**Cas**: JSON malformé dans `chassis_config`

```json
{
  "error": "Format JSON invalide pour chassis_config: Expecting property name enclosed in double quotes: line 1 column 2 (char 1)"
}
```

**Solution**: Vérifier la syntaxe JSON (guillemets doubles, virgules, accolades)

### Erreur 422 - Validation Pydantic

**Cas**: Valeurs hors limites (ex: `year=1900`, `quantity=-5`)

```json
{
  "error": "Erreur de validation",
  "detail": "Les données fournies sont invalides"
}
```

**Solution**: Respecter les contraintes (year: 1980-2055, quantity > 0, wmi: 3 caractères)

## Tests et exemples

### Test simple (180 châssis)

```bash
# 1. Upload et conversion
curl -X POST "http://localhost:8000/api/v1/convert" \
  -H "X-API-Key: votre_cle_api" \
  -F "file=@tests/RFCV-CHASSIS/FCVR-189.pdf" \
  -F "taux_douane=573.139" \
  -F 'chassis_config={"generate_chassis":true,"quantity":180,"wmi":"LZS","year":2025}' \
  -o response.json

# 2. Vérifier le XML généré
grep -c "Attached_document_code>6122" output/FCVR-189.xml
# Résultat attendu: 180

# 3. Vérifier les VIN
grep "Attached_document_reference>LZS" output/FCVR-189.xml | head -5
```

### Test avec limitation (50 châssis)

```bash
curl -X POST "http://localhost:8000/api/v1/convert" \
  -H "X-API-Key: votre_cle_api" \
  -F "file=@tests/RFCV-CHASSIS/FCVR-190.pdf" \
  -F "taux_douane=573.139" \
  -F 'chassis_config={"generate_chassis":true,"quantity":50,"wmi":"LZS","year":2025}' \
  -o response.json

# Articles 51-60 ne doivent PAS avoir de châssis
grep -c "Attached_document_code>6122" output/FCVR-190.xml
# Résultat attendu: 50 (pas plus)
```

### Test batch avec configs différentes

```bash
curl -X POST "http://localhost:8000/api/v1/batch" \
  -H "X-API-Key: votre_cle_api" \
  -F "files=@tests/RFCV-CHASSIS/FCVR-191.pdf" \
  -F "files=@tests/RFCV-CHASSIS/FCVR-193.pdf" \
  -F 'taux_douanes=[573.139, 573.139]' \
  -F 'chassis_configs=[
    {"generate_chassis":true,"quantity":75,"wmi":"LFV","year":2024},
    {"generate_chassis":true,"quantity":10,"wmi":"LZS","year":2025}
  ]' \
  -F "workers=2" \
  -o batch_response.json

# Récupérer le batch_id de la réponse
BATCH_ID=$(jq -r '.batch_id' batch_response.json)

# Attendre la fin du traitement
sleep 5

# Vérifier les résultats
curl -X GET "http://localhost:8000/api/v1/batch/$BATCH_ID/results" \
  -H "X-API-Key: votre_cle_api" | jq
```

## Bonnes pratiques

### 1. Validation des données

**Toujours valider**:
- Format JSON correct (guillemets doubles, virgules)
- Paramètres requis présents (`generate_chassis`, `quantity`, `wmi`, `year`)
- Valeurs dans les limites (year: 1980-2055, quantity > 0)

### 2. Gestion des séquences

**Unicité garantie**:
- `ensure_unique: true` (recommandé) → Persistance activée
- Séquences continues entre conversions
- Thread-safe pour traitement parallèle

**Vérifier les séquences**:
```bash
cat data/chassis_sequences.json
```

### 3. Performance

**Optimiser le traitement batch**:
- Utiliser `workers=4` (ou plus) pour parallélisation
- Regrouper les fichiers avec configs similaires
- Limiter la quantité de châssis si peu d'articles nécessitent

### 4. Sécurité

**Protection API**:
- Toujours utiliser HTTPS en production
- Clés API longues et aléatoires (≥16 caractères)
- Rate limiting activé par défaut

## Swagger UI

### Accès à la documentation interactive

**URL**: http://localhost:8000/docs

**Authentification dans Swagger**:
1. Cliquer sur "Authorize" (cadenas en haut à droite)
2. Entrer la clé API dans "APIKeyHeader"
3. Cliquer sur "Authorize"
4. Tester les endpoints directement

**Exemples pré-remplis**:
- Chaque endpoint contient des exemples complets
- Configuration chassis avec valeurs réalistes
- Commandes curl prêtes à copier

### ReDoc (documentation alternative)

**URL**: http://localhost:8000/redoc

Documentation en lecture seule avec:
- Navigation par tags (Conversion, Batch, Files, Health)
- Schémas de données détaillés
- Exemples de requêtes/réponses

## Dépannage

### Problème: Séquences dupliquées

**Symptôme**: VIN identiques générés

**Cause**: `ensure_unique: false` ou fichier `data/chassis_sequences.json` corrompu

**Solution**:
```bash
# Vérifier le fichier de séquences
cat data/chassis_sequences.json

# Réinitialiser si nécessaire (ATTENTION: perte de l'historique)
rm data/chassis_sequences.json
```

### Problème: Pas de châssis générés

**Symptôme**: Aucun document 6122 dans le XML

**Causes possibles**:
1. `generate_chassis: false` ou absent
2. `quantity: 0` ou absent
3. Code HS ne nécessite pas de châssis (pas 87xx)

**Vérification**:
```bash
# Vérifier les logs de conversion
tail -f logs/api.log

# Rechercher les messages de génération
grep "Châssis généré" logs/api.log
```

### Problème: Limitation non respectée

**Symptôme**: Plus de VIN générés que `quantity` spécifié

**Cause**: Appel API multiple avec même config

**Solution**: Chaque conversion génère `quantity` VIN. Pour limiter globalement, ajuster `quantity` en fonction des conversions précédentes.

## Exemples de code

### Python avec requests

```python
import requests
import json

# Configuration
api_url = "http://localhost:8000/api/v1/convert"
api_key = "votre_cle_api"

# Configuration chassis
chassis_config = {
    "generate_chassis": True,
    "quantity": 180,
    "wmi": "LZS",
    "year": 2025
}

# Paramètres de la requête
files = {"file": open("DOSSIER_18236.pdf", "rb")}
data = {
    "taux_douane": 573.139,
    "chassis_config": json.dumps(chassis_config)
}
headers = {"X-API-Key": api_key}

# Envoi de la requête
response = requests.post(api_url, files=files, data=data, headers=headers)

# Traitement de la réponse
if response.status_code == 200:
    result = response.json()
    print(f"✅ Conversion réussie: {result['output_file']}")
    print(f"Articles: {result['metrics']['items_count']}")
    print(f"Temps: {result['processing_time']}s")
else:
    print(f"❌ Erreur {response.status_code}: {response.json()}")
```

### JavaScript (Node.js) avec axios

```javascript
const axios = require('axios');
const FormData = require('form-data');
const fs = require('fs');

// Configuration
const apiUrl = 'http://localhost:8000/api/v1/convert';
const apiKey = 'votre_cle_api';

// Configuration chassis
const chassisConfig = {
  generate_chassis: true,
  quantity: 180,
  wmi: 'LZS',
  year: 2025
};

// Préparation de la requête
const form = new FormData();
form.append('file', fs.createReadStream('DOSSIER_18236.pdf'));
form.append('taux_douane', '573.139');
form.append('chassis_config', JSON.stringify(chassisConfig));

// Envoi de la requête
axios.post(apiUrl, form, {
  headers: {
    ...form.getHeaders(),
    'X-API-Key': apiKey
  }
})
.then(response => {
  console.log('✅ Conversion réussie:', response.data.output_file);
  console.log('Articles:', response.data.metrics.items_count);
  console.log('Temps:', response.data.processing_time + 's');
})
.catch(error => {
  console.error('❌ Erreur:', error.response?.data || error.message);
});
```

## Support

Pour toute question ou problème:
- **Documentation API**: http://localhost:8000/docs
- **Health check**: http://localhost:8000/api/v1/health
- **Logs**: `logs/api.log`
- **Tests manuels**: Voir `claudedocs/chassis_generation_tests.md`

---

**Version**: 2.1.0
**Date**: 2025-01-10
**Auteur**: Claude Code (Assistant IA)
