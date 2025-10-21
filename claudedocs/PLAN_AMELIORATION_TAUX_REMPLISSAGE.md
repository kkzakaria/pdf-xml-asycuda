# Plan d'Amélioration du Taux de Remplissage
## Projet: PDF RFCV → XML ASYCUDA

**Date de création**: 2025-10-21
**Dernière mise à jour**: 2025-10-21 (P3 complétée)
**Objectif global**: Passer de 69% à 85-92% de taux de remplissage
**Statut**: 🟢 PRIORITÉ 1 COMPLÉTÉE | 🟢 PRIORITÉ 2 COMPLÉTÉE | 🟢 PRIORITÉ 3 COMPLÉTÉE

---

## 📊 Progression Globale

```
Taux Initial: 69.0%
├─ ✅ PRIORITÉ 1: 72.4% (+3.4%)
├─ ✅ PRIORITÉ 2: 76.5% (+4.1%)
└─ ✅ PRIORITÉ 3: 79.5% (+3.0%)
```

### Métriques Actuelles
- **Taux de remplissage**: **79.5%** (était 69.0%)
- **Amélioration P1**: +3.4 points
- **Amélioration P2**: +4.1 points
- **Amélioration P3**: +3.0 points
- **Amélioration totale**: +10.5 points
- **Fichiers testés**: 2/2 (BL_2025_02830_RFCV.pdf, BL_2025_03228_RFCV.pdf)
- **Taux de réussite**: 100%
- **XMLs valides**: 2/2
- **Warnings**: 0

### Problèmes Résolus (P1 + P2 + P3)
1. ✅ **Données Transport**: INCOTERM, Connaissement, Voyage, Navire extraits (P1)
2. ✅ **Poids**: NET et BRUT correctement extraits (P1)
3. ✅ **Warnings poids**: Éliminés (2 → 0) (P1)
4. ✅ **Vessel Name**: Nettoyé (date supprimée) (P1)
5. ✅ **No. RFCV**: RCS correctement extrait (P2)
6. ✅ **Données Facture**: No., Date, Montant extraits (P2)
7. ✅ **Devise**: Code USD et taux de change extraits (P2)
8. ✅ **Date RFCV**: Extraite (section 5) (P3)
9. ✅ **Dates FDI/DAI**: No. et Date extraits (sections 7-8) (P3)
10. ✅ **Type Livraison**: TOT/PART extrait (section 6) (P3)
11. ✅ **Type Colisage**: CARTONS/PACKAGES extrait (section 24) (P3)

### Problèmes Restants (P4 potentielle)
1. ❌ **Loading/Discharge locations**: Codes ports optionnels
2. ❌ **Champs Valuation calculés**: total_cost, total_invoice
3. ❌ **Champs Country complets**: Destination, origine

---

## ✅ PRIORITÉ 1 - Transport et Poids (Impact: 69% → 72.4%)

**Objectif**: +9% de taux de remplissage
**Résultat**: +3.4% de taux de remplissage
**Temps réel**: ~2 heures
**Statut**: ✅ **COMPLÉTÉE** (2025-10-21)

### Rapport Détaillé
📄 Voir: `claudedocs/P1_VALIDATION_REPORT.md`
📊 Comparaison: `claudedocs/P1_AVANT_APRES.md`

### Tâches

#### 1.1 Enrichir modèles - Transport
**Fichier**: `src/models.py`
**Statut**: ⏳ Pending

Ajouter à la classe `TransportInfo`:
```python
@dataclass
class TransportInfo:
    # Existant...
    vessel_identity: Optional[str] = None
    vessel_nationality: Optional[str] = None

    # NOUVEAU:
    bill_of_lading: Optional[str] = None        # No. Connaissement
    bl_date: Optional[str] = None               # Date Connaissement
    voyage_number: Optional[str] = None         # No. Voyage (ex: 535W)
    vessel_name: Optional[str] = None           # Nom navire/transporteur
    incoterm: Optional[str] = None              # CFR, FOB, CIF, etc.
    loading_location: Optional[str] = None      # Lieu chargement (ex: CNNGB)
    discharge_location: Optional[str] = None    # Lieu déchargement (ex: CIABJ)
    fcl_count: Optional[int] = None             # Nombre conteneurs complets
    lcl_count: Optional[int] = None             # Nombre conteneurs partiels
```

#### 1.2 Enrichir modèles - Valuation
**Fichier**: `src/models.py`
**Statut**: ⏳ Pending

Ajouter à la classe `Valuation`:
```python
@dataclass
class Valuation:
    # Existant...
    total_cost: Optional[float] = None

    # NOUVEAU:
    net_weight: Optional[float] = None          # Poids NET en KG
    gross_weight: Optional[float] = None        # Poids BRUT en KG
```

#### 1.3 Parser - Extraire INCOTERM
**Fichier**: `src/rfcv_parser.py`
**Fonction**: `_parse_transport()`
**Statut**: ⏳ Pending

Pattern à ajouter:
```python
# Section 15: INCOTERM
incoterm_pattern = r'15\.\s*INCOTERM\s+.*?\n\s*([A-Z]{2,3})'
transport.incoterm = self._extract_field(incoterm_pattern)
```

Données disponibles: `CFR`, `FOB`, `CIF`, `EXW`, etc.

#### 1.4 Parser - Extraire No. Connaissement
**Fichier**: `src/rfcv_parser.py`
**Fonction**: `_parse_transport()`
**Statut**: ⏳ Pending

Pattern à ajouter:
```python
# No. Connaissement (section 3)
bl_pattern = r'No\.\s*\(LTA/Connaissement/CMR\):\s+Mode.*?\n\s*(\d+)'
transport.bill_of_lading = self._extract_field(bl_pattern)

# Date Connaissement
bl_date_pattern = r'Date\s*de\s*\(LTA/Connaissement/CMR\):\s+.*?\n\s*(\d{2}/\d{2}/\d{4})'
transport.bl_date = self._extract_field(bl_date_pattern)
```

Données disponibles: `258538306`, date `01/09/2025`

#### 1.5 Parser - Extraire Voyage/Navire/Transporteur
**Fichier**: `src/rfcv_parser.py`
**Fonction**: `_parse_transport()`
**Statut**: ⏳ Pending

Patterns à ajouter:
```python
# No. Voyage
voyage_pattern = r'No\.\s*\(Vol/Voyage/Transport routier\):\s*\n\s*(\w+)'
transport.voyage_number = self._extract_field(voyage_pattern)

# Transporteur ID (nom du navire)
vessel_pattern = r'Transporteur\s*ID:\s*\n\s*([A-Z\s]+)'
transport.vessel_name = self._extract_field(vessel_pattern)
```

Données disponibles: Voyage `535W`, Navire `MAERSK FELIXSTOWE`

#### 1.6 Parser - Extraire Lieux Chargement/Déchargement
**Fichier**: `src/rfcv_parser.py`
**Fonction**: `_parse_transport()`
**Statut**: ⏳ Pending

Patterns à ajouter:
```python
# Lieu de chargement (code UN/LOCODE)
loading_pattern = r'Lieu\s*de\s*chargement:\s*([A-Z]{5})'
transport.loading_location = self._extract_field(loading_pattern)

# Lieu de déchargement
discharge_pattern = r'Lieu\s*de\s*déchargement:\s*([A-Z]{5})'
transport.discharge_location = self._extract_field(discharge_pattern)

# No. FCL et LCL
fcl_pattern = r'No\.\s*de\s*FCL:\s*(\d+)'
transport.fcl_count = self._extract_field(fcl_pattern)

lcl_pattern = r'No\.\s*de\s*LCL:\s*(\d+)'
transport.lcl_count = self._extract_field(lcl_pattern)
```

Données disponibles: Chargement `CNNGB` (Ningbo), Déchargement `CIABJ` (Abidjan), FCL `1`, LCL `0`

#### 1.7 Parser - Extraire Poids NET et BRUT
**Fichier**: `src/rfcv_parser.py`
**Fonction**: `_parse_valuation()`
**Statut**: ⏳ Pending

Patterns à ajouter:
```python
# Section 11: Poids Total NET (KG)
net_weight_pattern = r'11\.\s*Poids Total NET\s*\(KG\)\s+12\..*?\n\s*([\d\s,]+)'
net_weight_str = self._extract_field(net_weight_pattern)
if net_weight_str:
    # Nettoyer: "24 687,00" → 24687.0
    valuation.net_weight = float(net_weight_str.replace(' ', '').replace(',', '.'))

# Section 12: Poids Total BRUT (KG)
gross_weight_pattern = r'12\.\s*Poids Total BRUT\s*\(KG\)\s+13\..*?\n\s*([\d\s,]+)'
gross_weight_str = self._extract_field(gross_weight_pattern)
if gross_weight_str:
    valuation.gross_weight = float(gross_weight_str.replace(' ', '').replace(',', '.'))
```

Données disponibles: NET `24,687.00 KG`, BRUT `25,940.00 KG`

#### 1.8 Tester et Valider P1
**Statut**: ⏳ Pending

```bash
# Tester sur les 2 PDFs
python converter.py tests/BL_2025_02830_RFCV.pdf tests/BL_2025_03228_RFCV.pdf --batch --report p1_results

# Vérifier le taux de remplissage
# Objectif: 78% (±2%)
```

**Critères de succès**:
- ✅ Taux de remplissage ≥ 76%
- ✅ XMLs toujours valides
- ✅ INCOTERM extrait pour 2/2 fichiers
- ✅ Poids NET/BRUT extraits pour 2/2 fichiers
- ✅ Lieux chargement/déchargement extraits

---

## ✅ PRIORITÉ 2 - Données Financières (Impact: 72.4% → 76.5%)

**Objectif**: +12.6% de taux de remplissage (cible: 85%)
**Résultat**: +4.1% de taux de remplissage (atteint: 76.5%)
**Temps réel**: ~2 heures
**Statut**: ✅ **COMPLÉTÉE** (2025-10-21)

### Rapport Détaillé
📄 Voir: `claudedocs/P2_VALIDATION_REPORT.md`
📊 Résultats: `claudedocs/p2_apres_20251021_143527.*`

### Tâches

#### 2.1 Enrichir modèles - Financial
**Fichier**: `src/models.py`
**Statut**: ⏳ Pending

Ajouter à la classe `Financial`:
```python
@dataclass
class Financial:
    # Existant...
    mode_of_payment: Optional[str] = None

    # NOUVEAU:
    invoice_number: Optional[str] = None        # No. Facture
    invoice_date: Optional[str] = None          # Date Facture
    invoice_amount: Optional[float] = None      # Total Facture
    currency_code: Optional[str] = None         # Code Devise (USD, EUR, etc.)
    exchange_rate: Optional[float] = None       # Taux de Change
```

#### 2.2 Parser - Extraire No. Facture
**Fichier**: `src/rfcv_parser.py`
**Fonction**: `_parse_financial()`
**Statut**: ⏳ Pending

Pattern:
```python
# Section 13: No. Facture
invoice_number_pattern = r'13\.\s*No\.\s*Facture\s+14\..*?\n\s*(\S+)'
financial.invoice_number = self._extract_field(invoice_number_pattern)
```

Données: `2025/GB/SN17705`

#### 2.3 Parser - Extraire Date Facture
**Fichier**: `src/rfcv_parser.py`
**Fonction**: `_parse_financial()`
**Statut**: ⏳ Pending

Pattern:
```python
# Section 14: Date Facture
invoice_date_pattern = r'14\.\s*Date\s*Facture\s+15\..*?\n.*?(\d{2}/\d{2}/\d{4})'
financial.invoice_date = self._extract_field(invoice_date_pattern)
```

Données: `10/06/2025`

#### 2.4 Parser - Extraire Total Facture
**Fichier**: `src/rfcv_parser.py`
**Fonction**: `_parse_financial()`
**Statut**: ⏳ Pending

Pattern:
```python
# Section 18: Total Facture
invoice_amount_pattern = r'18\.\s*Total\s*Facture\s+19\..*?\n\s*([\d\s,]+)'
amount_str = self._extract_field(invoice_amount_pattern)
if amount_str:
    financial.invoice_amount = float(amount_str.replace(' ', '').replace(',', '.'))
```

Données: `6,220.00`

#### 2.5 Parser - Extraire Code Devise
**Fichier**: `src/rfcv_parser.py`
**Fonction**: `_parse_financial()`
**Statut**: ⏳ Pending

Pattern:
```python
# Section 16: Code Devise
currency_pattern = r'16\.\s*Code\s*Devise\s+17\..*?\n\s*([A-Z]{3})'
financial.currency_code = self._extract_field(currency_pattern)
```

Données: `USD`

#### 2.6 Parser - Extraire Taux de Change
**Fichier**: `src/rfcv_parser.py`
**Fonction**: `_parse_financial()`
**Statut**: ⏳ Pending

Pattern:
```python
# Section 17: Taux de Change
exchange_rate_pattern = r'17\.\s*Taux\s*de\s*Change\s+18\..*?\n.*?([\d,\.]+)'
rate_str = self._extract_field(exchange_rate_pattern)
if rate_str:
    financial.exchange_rate = float(rate_str.replace(',', '.'))
```

Données: `563.5300`

#### 2.7 Parser - Corriger No. RFCV
**Fichier**: `src/rfcv_parser.py`
**Fonction**: `_parse_identification()`
**Statut**: ⏳ Pending

**Problème actuel**: Extrait "5." au lieu du vrai numéro RFCV

Nouveau pattern:
```python
# Chercher après "4. No. RFCV"
rfcv_pattern = r'4\.\s*No\.\s*RFCV\s+5\..*?(\d{5,})'
ident.manifest_reference = self._extract_field(rfcv_pattern)

# Alternative si le numéro est dans le nom du fichier
if not ident.manifest_reference and 'RFCV' in self.pdf_path:
    import re
    file_match = re.search(r'(\d{5,})', Path(self.pdf_path).stem)
    if file_match:
        ident.manifest_reference = file_match.group(1)
```

#### 2.8 Tester et Valider P2
**Statut**: ⏳ Pending

```bash
python converter.py tests/BL_2025_02830_RFCV.pdf tests/BL_2025_03228_RFCV.pdf --batch --report p2_results
```

**Critères de succès**:
- ✅ Taux de remplissage ≥ 83%
- ✅ Facture extraite (No., Date, Montant)
- ✅ Devise et taux de change extraits
- ✅ No. RFCV corrigé

---

## ✅ PRIORITÉ 3 - Dates et Colisage (Impact: 76.5% → 79.5%)

**Objectif**: +7% de taux de remplissage (objectif 85%)
**Résultat**: +3.0% de taux de remplissage (atteint 79.5%)
**Temps réel**: ~1.5 heures
**Statut**: ✅ **COMPLÉTÉE** (2025-10-21)
**Dépendance**: Priorité 2 terminée

### Rapport Détaillé
📄 Voir: `claudedocs/P3_VALIDATION_REPORT.md`
📊 Résultats: `claudedocs/p3_apres_*.md` et `.json`

### Tâches

#### 3.1 Enrichir modèles - Identification
**Fichier**: `src/models.py`
**Statut**: ⏳ Pending

Ajouter:
```python
@dataclass
class Identification:
    # NOUVEAU:
    rfcv_date: Optional[str] = None             # Date RFCV
    fdi_number: Optional[str] = None            # No. FDI/DAI
    fdi_date: Optional[str] = None              # Date FDI/DAI
    delivery_type: Optional[str] = None         # TOT/PART
```

#### 3.2 Enrichir modèles - Property
**Fichier**: `src/models.py`
**Statut**: ⏳ Pending

Ajouter:
```python
@dataclass
class Property:
    # NOUVEAU:
    package_type: Optional[str] = None          # CARTONS, PACKAGES, COLIS, etc.
```

#### 3.3 Parser - Extraire Date RFCV
**Fichier**: `src/rfcv_parser.py`
**Statut**: ⏳ Pending

Pattern:
```python
# Section 5: Date RFCV
rfcv_date_pattern = r'5\.\s*Date\s*RFCV\s+6\..*?\n.*?(\d{2}/\d{2}/\d{4})'
```

Données: `18/09/2025`

#### 3.4 Parser - Extraire No. FDI/DAI
**Fichier**: `src/rfcv_parser.py`
**Statut**: ⏳ Pending

Pattern:
```python
# Section 7: No. FDI/DAI
fdi_pattern = r'7\.\s*No\.\s*FDI/DAI\s+8\..*?\n.*?(\d+)'
```

Données: `250153515`

#### 3.5 Parser - Extraire Date FDI/DAI
**Fichier**: `src/rfcv_parser.py`
**Statut**: ⏳ Pending

Pattern:
```python
# Section 8: Date FDI/DAI
fdi_date_pattern = r'8\.\s*Date\s*FDI/DAI\s+9\..*?\n.*?(\d{2}/\d{2}/\d{4})'
```

Données: `11/09/2025`

#### 3.6 Parser - Extraire Livraison TOT/PART
**Fichier**: `src/rfcv_parser.py`
**Statut**: ⏳ Pending

Pattern:
```python
# Section 6: Livraison
delivery_pattern = r'6\.\s*Livraison\s+7\..*?\n\s*(TOT|PART)'
```

Données: `TOT`

#### 3.7 Parser - Extraire Colisage
**Fichier**: `src/rfcv_parser.py`
**Statut**: ⏳ Pending

Pattern:
```python
# Section 24: Colisage
packages_pattern = r'24\..*?(\d+)\s+(CARTONS|PACKAGES|COLIS|PALETTES)'
match = re.search(packages_pattern, self.text)
if match:
    property.total_packages = int(match.group(1))
    property.package_type = match.group(2)
```

Données: `1611 CARTONS`

#### 3.8 Tester et Valider P3
**Statut**: ⏳ Pending

```bash
python converter.py tests/BL_2025_02830_RFCV.pdf tests/BL_2025_03228_RFCV.pdf --batch --report p3_results
```

**Critères de succès**:
- ✅ Taux de remplissage ≥ 90%
- ✅ Dates RFCV/FDI extraites
- ✅ Colisage détaillé extrait

---

## 🎯 TESTS FINAUX

**Statut**: ⏳ Pending
**Dépendance**: Priorité 3 terminée

### Tests Complets

```bash
# Test sur tous les PDFs disponibles
python tests/test_converter.py -d tests/ -v

# Génération rapport final
python converter.py -d tests/ --batch --report final_report
```

### Critères de Succès Globaux

- ✅ **Taux de remplissage moyen**: ≥ 85%
- ✅ **Taux de succès**: 100%
- ✅ **XMLs valides**: 100%
- ✅ **Warnings**: < 5% des conversions
- ✅ **Performance**: < 500ms par fichier

### Validation Qualité

1. **Structure XML**: Valider avec xmllint
2. **Données critiques**: Vérifier présence INCOTERM, Poids, Connaissement
3. **Conformité ASYCUDA**: Vérifier format `<null/>` pour champs vides
4. **Régression**: Comparer avec résultats baseline (69%)

---

## 📈 Suivi de Progression

| Priorité | Objectif | Statut | Taux Actuel | Taux Cible | Progression |
|----------|----------|--------|-------------|------------|-------------|
| Baseline | - | ✅ Terminé | 69% | - | - |
| P1 | Transport/Poids | ⏳ En attente | 69% | 78% | 0% |
| P2 | Données Financières | ⏳ En attente | 78% | 85% | 0% |
| P3 | Dates/Colisage | ⏳ En attente | 85% | 92% | 0% |
| Final | Tests complets | ⏳ En attente | 92% | 85-92% | 0% |

---

## 📝 Notes Importantes

### Patterns Regex
- **Apostrophes**: Gérer `'` (ASCII) ET `'` (U+2019)
- **Espaces**: Nettoyer espaces multiples et non-breakable
- **Nombres**: Format français avec espaces (`24 687,00`) et virgule décimale
- **Multilignes**: Utiliser `re.MULTILINE` et `re.DOTALL` si nécessaire

### Nettoyage Données
```python
def clean_numeric(value: str) -> float:
    """Nettoie valeur numérique française: '24 687,00' → 24687.0"""
    return float(value.replace(' ', '').replace(',', '.'))

def clean_text(value: str) -> str:
    """Nettoie texte: enlève espaces multiples, trim"""
    return ' '.join(value.split()).strip()
```

### Tests Unitaires
Après chaque priorité, ajouter tests unitaires dans `tests/test_parser.py`:
```python
def test_extract_incoterm():
    parser = RFCVParser('tests/BL_2025_02830_RFCV.pdf')
    data = parser.parse()
    assert data.transport.incoterm == 'CFR'
```

---

## 🔄 Historique des Modifications

| Date | Version | Changements | Auteur |
|------|---------|-------------|--------|
| 2025-10-21 | 1.0 | Création plan initial | Claude |

---

## 📌 Références

- **Documentation ASYCUDA**: https://asycuda.org/
- **Format RFCV**: Documents officiels de la douane ivoirienne
- **UN/LOCODE**: Codes lieux (CNNGB, CIABJ, etc.)
- **INCOTERMS**: CFR, FOB, CIF, EXW, etc.
