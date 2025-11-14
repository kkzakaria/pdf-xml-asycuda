# Endpoints API Spécifiques - PDF XML ASYCUDA

Documentation des endpoints API spécialisés pour chaque paramètre optionnel.

## Vue d'ensemble

L'API propose désormais **3 nouveaux endpoints spécialisés** en plus de l'endpoint générique `/convert` :

| Endpoint | Usage | Paramètres optionnels |
|----------|-------|----------------------|
| `/convert` | Conversion basique | ✅ Rapport et/ou châssis (optionnels) |
| `/convert/with-payment` | Avec rapport de paiement | ❌ Aucun (rapport obligatoire) |
| `/convert/with-chassis` | Avec génération châssis | ❌ Aucun (config châssis obligatoire) |
| `/convert/complete` | Conversion complète | ❌ Aucun (rapport + châssis obligatoires) |

---

## 1️⃣ Endpoint : `/convert/with-payment`

### Description
Conversion synchrone avec numéro de rapport de paiement (quittance du Trésor Public).

### Cas d'usage
Utilisez cet endpoint quand vous avez **DÉJÀ** le numéro de quittance du Trésor Public après paiement des taxes douanières.

### Workflow typique
1. **Conversion initiale** → `/convert` (sans rapport)
2. **Calcul des taxes** → ASYCUDA calcule les montants
3. **Paiement au Trésor** → Obtention du numéro de quittance (ex: 25P2003J)
4. **Re-conversion** → `/convert/with-payment` pour inclure le numéro

### Paramètres

| Paramètre | Type | Obligatoire | Description | Exemple |
|-----------|------|-------------|-------------|---------|
| `file` | File | ✅ | Fichier PDF RFCV | DOSSIER.pdf |
| `taux_douane` | float | ✅ | Taux de change douanier | 573.139 |
| `rapport_paiement` | string | ✅ | Numéro quittance Trésor | 25P2003J |

### Exemple cURL

```bash
curl -X POST "http://localhost:8000/api/v1/convert/with-payment" \
  -H "X-API-Key: votre_cle_api" \
  -F "file=@DOSSIER.pdf" \
  -F "taux_douane=573.139" \
  -F "rapport_paiement=25P2003J"
```

### Résultat XML

```xml
<Financial>
  <Deffered_payment_reference>25P2003J</Deffered_payment_reference>
  <Mode_of_payment>COMPTE DE PAIEMENT</Mode_of_payment>
</Financial>
```

---

## 2️⃣ Endpoint : `/convert/with-chassis`

### Description
Conversion synchrone avec génération automatique de numéros de châssis VIN ISO 3779.

### Cas d'usage
Utilisez cet endpoint pour générer automatiquement des VIN uniques pour les véhicules sans châssis dans le RFCV.

### Fonctionnalités
- ✅ Génération VIN ISO 3779 avec checksum
- ✅ Séquences persistantes (pas de doublons)
- ✅ Thread-safe pour traitement parallèle
- ✅ Nettoyage automatique des anciens châssis dans descriptions
- ✅ Documents code 6022 (motos) et 6122 (autres véhicules)

### Paramètres

| Paramètre | Type | Obligatoire | Description | Exemple | Défaut |
|-----------|------|-------------|-------------|---------|--------|
| `file` | File | ✅ | Fichier PDF RFCV | DOSSIER.pdf | - |
| `taux_douane` | float | ✅ | Taux de change douanier | 573.139 | - |
| `quantity` | int | ✅ | Nombre de VIN à générer | 180 | - |
| `wmi` | string(3) | ✅ | Code fabricant | LZS, LFV | - |
| `year` | int | ✅ | Année de fabrication | 2025 | - |
| `vds` | string(5) | ❌ | Descripteur véhicule | BA01A | HCKZS |
| `plant_code` | string(1) | ❌ | Code usine | P | S |

### Exemple cURL - 180 châssis LZS/2025

```bash
curl -X POST "http://localhost:8000/api/v1/convert/with-chassis" \
  -H "X-API-Key: votre_cle_api" \
  -F "file=@DOSSIER.pdf" \
  -F "taux_douane=573.139" \
  -F "quantity=180" \
  -F "wmi=LZS" \
  -F "year=2025"
```

### Exemple cURL - 50 châssis LFV/2024 avec VDS personnalisé

```bash
curl -X POST "http://localhost:8000/api/v1/convert/with-chassis" \
  -H "X-API-Key: votre_cle_api" \
  -F "file=@DOSSIER.pdf" \
  -F "taux_douane=573.139" \
  -F "quantity=50" \
  -F "wmi=LFV" \
  -F "year=2024" \
  -F "vds=BA01A" \
  -F "plant_code=P"
```

### Résultat XML

```xml
<Item>
  <!-- Document châssis (code 6122) -->
  <Attached_documents>
    <Attached_document_code>6122</Attached_document_code>
    <Attached_document_name>CHASSIS VEHICULES</Attached_document_name>
    <Attached_document_reference>LZSHCKZS0SS000001</Attached_document_reference>
    <Attached_document_from_rule>1</Attached_document_from_rule>
  </Attached_documents>

  <!-- Châssis dans Marks2 avec préfixe CH: -->
  <Packages>
    <Marks1_of_packages>TRICYCLE AP150ZK</Marks1_of_packages>
    <Marks2_of_packages>CH: LZSHCKZS0SS000001</Marks2_of_packages>
  </Packages>

  <!-- Description nettoyée -->
  <Goods_description>
    <Description_of_goods>TRICYCLE AP150ZK</Description_of_goods>
  </Goods_description>
</Item>
```

---

## 3️⃣ Endpoint : `/convert/complete`

### Description
Conversion synchrone complète avec rapport de paiement **ET** génération de châssis VIN.

### Cas d'usage
Utilisez cet endpoint pour une conversion incluant **TOUTES** les fonctionnalités :
- ✅ Numéro de quittance du Trésor Public
- ✅ Génération automatique de châssis VIN ISO 3779
- ✅ Toutes les fonctionnalités combinées

### Paramètres

| Paramètre | Type | Obligatoire | Description | Exemple | Défaut |
|-----------|------|-------------|-------------|---------|--------|
| `file` | File | ✅ | Fichier PDF RFCV | DOSSIER.pdf | - |
| `taux_douane` | float | ✅ | Taux de change douanier | 573.139 | - |
| `rapport_paiement` | string | ✅ | Numéro quittance Trésor | 25P2003J | - |
| `quantity` | int | ✅ | Nombre de VIN à générer | 180 | - |
| `wmi` | string(3) | ✅ | Code fabricant | LZS | - |
| `year` | int | ✅ | Année de fabrication | 2025 | - |
| `vds` | string(5) | ❌ | Descripteur véhicule | BA01A | HCKZS |
| `plant_code` | string(1) | ❌ | Code usine | P | S |

### Exemple cURL

```bash
curl -X POST "http://localhost:8000/api/v1/convert/complete" \
  -H "X-API-Key: votre_cle_api" \
  -F "file=@DOSSIER.pdf" \
  -F "taux_douane=573.139" \
  -F "rapport_paiement=25P2003J" \
  -F "quantity=180" \
  -F "wmi=LZS" \
  -F "year=2025"
```

### Résultat XML

Le XML généré contiendra **à la fois** :

```xml
<!-- Rapport de paiement -->
<Financial>
  <Deffered_payment_reference>25P2003J</Deffered_payment_reference>
  <Mode_of_payment>COMPTE DE PAIEMENT</Mode_of_payment>
</Financial>

<!-- Châssis VIN générés -->
<Item>
  <Attached_documents>
    <Attached_document_code>6122</Attached_document_code>
    <Attached_document_reference>LZSHCKZS0SS000001</Attached_document_reference>
  </Attached_documents>
  <Packages>
    <Marks2_of_packages>CH: LZSHCKZS0SS000001</Marks2_of_packages>
  </Packages>
</Item>
```

---

## Comparaison des endpoints

### Tableau de décision

| Scénario | Endpoint recommandé | Raison |
|----------|-------------------|--------|
| Conversion basique sans options | `/convert` | Endpoint générique flexible |
| Vous avez le numéro de quittance | `/convert/with-payment` | API claire et explicite |
| Besoin de générer des châssis | `/convert/with-chassis` | Configuration simplifiée |
| Conversion complète post-paiement | `/convert/complete` | Toutes fonctionnalités activées |
| Conversion avec options variables | `/convert` | Paramètres optionnels flexibles |

### Avantages des endpoints spécialisés

**Clarté de l'API** :
- ✅ Intentions explicites dans l'URL
- ✅ Paramètres obligatoires vs optionnels clairement définis
- ✅ Documentation Swagger plus lisible

**Validation stricte** :
- ✅ Validation des paramètres requis automatique
- ✅ Moins d'erreurs dues aux paramètres manquants
- ✅ Messages d'erreur plus précis

**Expérience développeur** :
- ✅ Autocomplétion IDE plus pertinente
- ✅ Moins de logique conditionnelle côté client
- ✅ Tests unitaires plus simples

---

## Réponses de l'API

### Succès (200 OK)

```json
{
  "success": true,
  "job_id": "conv_abc123xyz",
  "filename": "DOSSIER_18236.pdf",
  "output_file": "DOSSIER_18236.xml",
  "message": "Conversion réussie avec génération de 180 châssis VIN",
  "metrics": {
    "items_count": 180,
    "containers_count": 2,
    "fill_rate": 68.5,
    "warnings_count": 0,
    "warnings": [],
    "xml_valid": true,
    "has_exporter": true,
    "has_consignee": true,
    "processing_time": 1.24
  },
  "processing_time": 1.24
}
```

### Erreurs

**400 Bad Request** - Paramètres invalides :
```json
{
  "detail": "Taux invalide: doit être > 0"
}
```

**422 Validation Error** - Champs manquants :
```json
{
  "detail": [
    {
      "loc": ["body", "rapport_paiement"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

**500 Internal Server Error** - Erreur de conversion :
```json
{
  "detail": "Erreur lors de la conversion: Invalid PDF structure"
}
```

---

## Documentation interactive

Accédez à la documentation Swagger interactive :

- **Swagger UI** : http://localhost:8000/docs
- **ReDoc** : http://localhost:8000/redoc

Tous les nouveaux endpoints sont documentés avec :
- ✅ Descriptions détaillées
- ✅ Exemples de requêtes cURL
- ✅ Schémas de validation
- ✅ Exemples de réponses
- ✅ Bouton "Try it out" pour tests en temps réel

---

## Migration depuis l'endpoint générique

### Avant (endpoint générique)

```bash
# Avec rapport de paiement
curl -X POST "http://localhost:8000/api/v1/convert" \
  -F "file=@DOSSIER.pdf" \
  -F "taux_douane=573.139" \
  -F "rapport_paiement=25P2003J"

# Avec châssis (JSON complexe)
curl -X POST "http://localhost:8000/api/v1/convert" \
  -F "file=@DOSSIER.pdf" \
  -F "taux_douane=573.139" \
  -F 'chassis_config={"generate_chassis":true,"quantity":180,"wmi":"LZS","year":2025}'
```

### Après (endpoints spécialisés)

```bash
# Avec rapport de paiement (plus simple)
curl -X POST "http://localhost:8000/api/v1/convert/with-payment" \
  -F "file=@DOSSIER.pdf" \
  -F "taux_douane=573.139" \
  -F "rapport_paiement=25P2003J"

# Avec châssis (paramètres directs)
curl -X POST "http://localhost:8000/api/v1/convert/with-chassis" \
  -F "file=@DOSSIER.pdf" \
  -F "taux_douane=573.139" \
  -F "quantity=180" \
  -F "wmi=LZS" \
  -F "year=2025"
```

### Rétrocompatibilité

L'endpoint générique `/convert` reste **100% fonctionnel** :
- ✅ Pas de breaking changes
- ✅ Tous les paramètres optionnels toujours disponibles
- ✅ Migration progressive possible

---

## Exemples d'intégration

### Python (requests)

```python
import requests

# Endpoint spécialisé avec rapport
url = "http://localhost:8000/api/v1/convert/with-payment"
headers = {"X-API-Key": "votre_cle_api"}
files = {"file": open("DOSSIER.pdf", "rb")}
data = {
    "taux_douane": 573.139,
    "rapport_paiement": "25P2003J"
}

response = requests.post(url, headers=headers, files=files, data=data)
result = response.json()

print(f"Succès: {result['success']}")
print(f"XML généré: {result['output_file']}")
```

### JavaScript (Fetch API)

```javascript
const formData = new FormData();
formData.append('file', fileInput.files[0]);
formData.append('taux_douane', '573.139');
formData.append('quantity', '180');
formData.append('wmi', 'LZS');
formData.append('year', '2025');

const response = await fetch('http://localhost:8000/api/v1/convert/with-chassis', {
  method: 'POST',
  headers: {
    'X-API-Key': 'votre_cle_api'
  },
  body: formData
});

const result = await response.json();
console.log('Châssis générés:', result.message);
```

---

## Limitations et notes

### Limitations des endpoints spécialisés

1. **Pas de mode asynchrone** : Les endpoints spécialisés sont synchrones uniquement
   - **Workaround** : Utiliser `/convert/async` avec paramètres optionnels

2. **Pas de batch** : Un seul fichier par requête
   - **Workaround** : Utiliser `/batch` pour traitement parallèle

### Performance

Les endpoints spécialisés ont les **mêmes performances** que l'endpoint générique :
- Temps de conversion : ~1.2s pour 180 châssis
- Taux de succès : 100% (198/198 tests)
- Thread-safe : Oui

### Sécurité

Tous les endpoints nécessitent :
- ✅ Header `X-API-Key` obligatoire
- ✅ Validation MIME type des fichiers
- ✅ Taille maximale : 50MB par fichier
- ✅ Rate limiting activé (configurable)
