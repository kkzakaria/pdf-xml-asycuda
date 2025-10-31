# Analyse - Place of Loading (Lieu de Chargement)

**Date**: 2025-10-31

## 📋 Structure Complète

### 1️⃣ Modèle de Données (`models.py:62-72`)

```python
@dataclass
class TransportInfo:
    # Champs historiques
    loading_place_code: Optional[str] = None      # Code UN/LOCODE (5 caractères)
    loading_place_name: Optional[str] = None      # Nom du lieu de chargement

    # Champs PRIORITÉ 1 (ajoutés)
    loading_location: Optional[str] = None        # Code UN/LOCODE (alias)
```

### 2️⃣ Génération XML (`xml_generator.py:331-336`)

```xml
<Transport>
  <Place_of_loading>
    <Code>CNNGB</Code>                 <!-- Code UN/LOCODE -->
    <Name/>                            <!-- Nom du lieu (vide) -->
    <Country>
      <null/>
    </Country>
  </Place_of_loading>
</Transport>
```

**Logique génération** (ligne 333):
```python
loading_code = trans.loading_location if trans and trans.loading_location else (trans.loading_place_code if trans and trans.loading_place_code else '')
self._add_simple_element(loading, 'Code', loading_code)
self._add_simple_element(loading, 'Name', trans.loading_place_name if trans and trans.loading_place_name else '')
```

### 3️⃣ Extraction RFCV (`rfcv_parser.py:392-404`)

#### Code UN/LOCODE (Section RFCV)
```python
# Pattern: "Lieu de chargement: CNNGB"
loading = self._extract_field(r'Lieu\s*de\s*chargement:\s*([A-Z]{5})')
if loading:
    transport.loading_place_code = loading  # Ex: CNNGB
    transport.loading_location = loading    # Alias
```

#### Nom du Lieu (Section 15: INCOTERM)
```python
# Pattern: cherche entre INCOTERM et "16. Code Devise"
loading_match = re.search(r'\b(CFR|FOB|CIF|...)\b\s*\n([A-Z][A-Z\s]+?)\s+16\.', self.text)
if loading_match:
    transport.loading_place_name = loading_match.group(2).strip()
```

## 📄 Exemple RFCV Réel

### Source PDF (`tests/BL_2025_02830_RFCV.pdf`)

**Section transport**:
```
Lieu de chargement: CNNGB
Lieu de transbordement:
Lieu de déchargement: CIABJ
```

**Section 15 (INCOTERM)**:
```
15. INCOTERM
BUSINESS CENTRE SHARJAH PUBLISHING CITY FREE ZONE
2025/GB/SN17705 10/06/2025 CFR
16. Code Devise
```

### Résultat Extraction

| Champ | Valeur Extraite | Source |
|-------|-----------------|--------|
| `loading_place_code` | `CNNGB` | ✅ "Lieu de chargement:" |
| `loading_location` | `CNNGB` | ✅ "Lieu de chargement:" (alias) |
| `loading_place_name` | `None` | ❌ Pattern ne capture pas |

### XML Généré

```xml
<Place_of_loading>
  <Code>CNNGB</Code>           <!-- ✅ Extrait -->
  <Name/>                      <!-- ❌ Vide -->
  <Country>
    <null/>
  </Country>
</Place_of_loading>
```

## 🔍 Analyse du Problème

### Pattern d'Extraction Actuel

**Pattern** (ligne 402):
```python
r'\b(CFR|FOB|CIF|EXW|FCA|CPT|CIP|DAP|DPU|DDP)\b\s*\n([A-Z][A-Z\s]+?)\s+16\.'
```

**Recherche** : `INCOTERM` suivi d'un retour ligne, puis le nom du lieu, puis "16. Code Devise"

**Problème** : Dans le PDF test, la structure est :
```
15. INCOTERM
BUSINESS CENTRE SHARJAH PUBLISHING CITY FREE ZONE   ← Nom du lieu
2025/GB/SN17705 10/06/2025 CFR                       ← INCOTERM sur ligne avec dates
16. Code Devise
```

Le pattern cherche du texte **APRÈS** l'INCOTERM, mais le nom du lieu est **AVANT**.

### Structure Réelle RFCV

**Format observé** :
```
15. INCOTERM
<NOM_DU_LIEU>
<facture> <date> <INCOTERM>
16. Code Devise
```

**Pattern devrait capturer** : La ligne entre "15. INCOTERM" et la ligne contenant l'INCOTERM lui-même.

## 🎯 Codes UN/LOCODE Courants

| Code | Lieu | Pays |
|------|------|------|
| **CNNGB** | Ningbo | Chine |
| **CNSHA** | Shanghai | Chine |
| **CNQGD** | Qingdao | Chine |
| **CNYTN** | Yantian | Chine |
| **CIABJ** | Abidjan | Côte d'Ivoire |
| **AEJEA** | Jebel Ali | Émirats Arabes Unis |

**Standard** : [ISO 3166-1 alpha-2] + [code lieu 3 lettres]
- Exemple: CN (Chine) + NGB (Ningbo) = CNNGB

## ✅ État Actuel

### Fonctionnel ✅
- **Code UN/LOCODE** : Correctement extrait et généré dans XML
- **Champ `<Code>`** : Rempli avec code 5 caractères (ex: CNNGB)

### Non Fonctionnel ❌
- **Nom du lieu** : Non extrait du RFCV (reste vide)
- **Champ `<Name>`** : Vide dans XML

### Impact

**ASYCUDA** : Le code UN/LOCODE suffit généralement pour identifier le lieu de chargement. Le nom est informatif mais non critique.

**Conformité** : ✅ La structure XML est valide même avec `<Name/>` vide.

## 📝 Options

### Option 1: Laisser vide (Actuel)
- ✅ Code UN/LOCODE suffit
- ✅ Pas de risque d'extraction incorrecte
- ❌ Information incomplète

### Option 2: Corriger le pattern d'extraction
- ✅ Information complète dans XML
- ⚠️ Nécessite validation pattern sur plusieurs RFCV
- ⚠️ Structure RFCV peut varier

### Option 3: Mapping code → nom
- ✅ Nom systématiquement présent
- ✅ Pas de dépendance au format RFCV
- ⚠️ Nécessite maintenir table de correspondance

## 🎯 Recommandation

**Option 1 (Statu quo)** est recommandée car :
- Le code UN/LOCODE est l'identifiant officiel
- ASYCUDA reconnaît le lieu via le code
- Le nom est redondant avec le code
- Évite les erreurs d'extraction de texte

Si le nom est requis, **Option 3 (Mapping)** est plus robuste que l'extraction depuis PDF.

## 📚 Références

- **UN/LOCODE** : https://unece.org/trade/cefact/unlocode-code-list-country-and-territory
- **ASYCUDA Transport** : Section Place_of_loading avec Code obligatoire, Name optionnel
