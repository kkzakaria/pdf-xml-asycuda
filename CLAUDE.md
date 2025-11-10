# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PDF RFCV → XML ASYCUDA Converter: A Python-based automation tool that extracts structured data from RFCV (Rapport Final de Contrôle et de Vérification) PDF documents and generates XML files compatible with the ASYCUDA customs system used in Côte d'Ivoire.

## Development Commands

### Testing

```bash
# Run API tests with pytest
python -m pytest tests/api/ -v

# Run converter tests (generates reports)
python tests/test_converter.py -d tests/ -v

# Run converter tests without reports
python tests/test_converter.py -d tests/ --no-report

# Run specific test file
python -m pytest tests/api/test_convert.py -v
```

### Running the Application

```bash
# Start FastAPI server (development)
python run_api.py

# Start with uvicorn directly
python3 -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# CLI conversion - single file
python converter.py "DOSSIER 18236.pdf" -v

# CLI batch processing with parallel workers
python converter.py -d tests/ --batch --workers 4 --report batch_results
```

### Docker

```bash
# Build Docker image
docker build -t pdf-xml-asycuda .

# Run container
docker run -p 8000:8000 pdf-xml-asycuda

# Using docker-compose
docker-compose up -d
```

### Linting

```bash
# Run Ruff linter (used in CI)
ruff check src/ --output-format=github

# Check Python syntax
python -m py_compile src/**/*.py
```

### Testing Chassis Detection

```bash
# Run chassis detection tests
python -m pytest tests/test_chassis_detection.py -v

# Test on real RFCV with vehicles
python converter.py "tests/DOSSIER 18237.pdf" -o output/test_chassis.xml -v

# Run article grouping tests
python -m pytest tests/test_item_grouping.py -v
```

## Chassis Detection Feature

The system automatically detects and extracts chassis/VIN numbers for vehicles based on HS codes.

### Supported HS Codes (Chapter 87 - Vehicles)

Vehicles requiring chassis numbers (codes HS à 4 chiffres):

| Code HS | Type de Véhicule | Format |
|---------|------------------|--------|
| **8701** | Tracteurs | VIN 17 caractères |
| **8702** | Bus/Autocars (≥10 places) | VIN 17 caractères |
| **8703** | Voitures automobiles | VIN 17 caractères |
| **8704** | Camions, tricycles | Châssis 13-17 caractères |
| **8705** | Véhicules à usages spéciaux | VIN 17 caractères |
| **8711** | Motocycles, cyclomoteurs | Châssis/VIN 13-17 caractères |
| **8427** | Chariots de manutention | Châssis variable |
| **8429** | Engins de travaux publics | Châssis variable |
| **8716** | Remorques, semi-remorques | Châssis variable |

### Extraction Patterns

Le système détecte automatiquement:
- **VIN standard**: 17 caractères (norme ISO 3779, pas de I/O/Q)
- **Châssis fabricant**: 13-17 caractères alphanumériques
- **Préfixes explicites**: `CH:`, `CHASSIS:`, `VIN:` suivis du numéro

Exemples:
```
"TRICYCLE AP150ZH-20 LLCLHJL03SP420331" → Châssis: LLCLHJL03SP420331
"MOTORCYCLE LRFPCJLDIS0F18969" → VIN: LRFPCJLDIS0F18969
"MOTO CH: ABC123DEF456GHI" → Châssis: ABC123DEF456GHI
```

### XML Output Format (ASYCUDA Standard)

Pour chaque véhicule avec châssis détecté:

```xml
<Item>
  <!-- Document châssis (code 6122) -->
  <Attached_documents>
    <Attached_document_code>6122</Attached_document_code>
    <Attached_document_name>CHASSIS MOTOS</Attached_document_name>
    <Attached_document_reference>LLCLHJL03SP420331</Attached_document_reference>
    <Attached_document_from_rule>1</Attached_document_from_rule>
  </Attached_documents>

  <!-- Châssis dans Marks2 avec préfixe CH: -->
  <Packages>
    <Marks1_of_packages>TRICYCLE AP150ZH-20</Marks1_of_packages>
    <Marks2_of_packages>CH: LLCLHJL03SP420331</Marks2_of_packages>
  </Packages>

  <!-- Description nettoyée (châssis retiré) -->
  <Goods_description>
    <Description_of_goods>TRICYCLE AP150ZH-20</Description_of_goods>
  </Goods_description>
</Item>
```

### Implementation Files

- `src/hs_code_rules.py`: Liste officielle des codes HS nécessitant châssis
- `src/rfcv_parser.py`: Détection et extraction des numéros de châssis
- `src/xml_generator.py`: Génération document code 6122 + Marks2
- `src/models.py`: Modèle `Package` avec champ `chassis_number`
- `tests/test_chassis_detection.py`: 22 tests unitaires (100% pass)

### Fallback Detection

Si le code HS est absent ou invalide, détection par mots-clés:
- MOTORCYCLE, MOTO, SCOOTER
- TRICYCLE, THREE WHEEL
- VEHICLE, CAR, TRUCK
- TRACTOR, BUS, BULLDOZER

Confiance: 70% (vs 100% pour détection par code HS)

### Logging

Le système log automatiquement:
```
INFO: Article 1: Châssis détecté (Véhicules transport marchandises) - LLCLHJL03SP420331
WARNING: Article 5: Code HS 8704 nécessite un châssis mais aucun détecté dans description
```

## Article Grouping by HS Code (Regroupement d'articles)

The system automatically groups articles without chassis numbers that share the same HS code (Code SH Attesté) to simplify customs declarations.

### Grouping Rules

- **Articles with chassis**: NEVER grouped (each vehicle must be declared individually)
- **Articles without chassis**: Grouped ONLY if multiple articles share the same HS code
- **No grouping if all HS codes are different**: Quantities remain unchanged
- **Quantity handling** (when grouping occurs):
  - First article of first group receives the total package count (section 24)
  - Other articles receive quantity = 0
- **Package count preserved**: The total from section "24. Colisage, nombre et désignation des marchandises" remains unchanged

### Grouping Process

1. **Separation**: Articles are split into two categories:
   - Articles WITH chassis (preserved individually)
   - Articles WITHOUT chassis (candidates for grouping)

2. **Grouping**: Articles without chassis are grouped by full HS code:
   ```
   Example Input (35 articles without chassis):
   - 10 articles HS 8703.23.19.00
   - 15 articles HS 8704.21.10.00
   - 10 articles HS 8711.20.90.00

   Output: 3 representative articles
   ```

3. **Quantity Assignment**:
   - First article of first group: `quantity = total_packages` (from section 24)
   - All other articles: `quantity = 0`
   - If `total_packages` is None: quantities remain unchanged

4. **Recombination**: Final list = articles with chassis + grouped articles

### Example Scenarios

#### Scenario 1: With Grouping (Same HS Codes)

**RFCV Input**:
- Section 24: "35 CARTONS"
- Section 26 Articles:
  - 2 MOTORCYCLE with chassis VIN123... (HS 8711.20.90.00)
  - 10 TRICYCLE without chassis (HS 8704.21.10.00)
  - 15 MOTO without chassis (HS 8711.20.90.00)
  - 8 SCOOTER without chassis (HS 8711.20.90.00)

**XML Output**:
- 4 total articles in declaration:
  1. MOTORCYCLE #1 (with chassis VIN123..., quantity = original)
  2. MOTORCYCLE #2 (with chassis VIN456..., quantity = original)
  3. TRICYCLE representative (HS 8704, **quantity = 35** ← total_packages)
  4. MOTO representative (HS 8711, quantity = 0)

#### Scenario 2: No Grouping (All Different HS Codes)

**RFCV Input**:
- Section 24: "1611 CARTONS"
- Section 26 Articles:
  - Article 1: PARTS FOR ENGINES (HS 84099900, quantity 816)
  - Article 2: AIR COMPRESSOR (HS 84148090, quantity 795)

**XML Output**:
- 2 total articles in declaration (unchanged):
  1. PARTS FOR ENGINES (HS 84099900, **quantity = 816** ← inchangée)
  2. AIR COMPRESSOR (HS 84148090, **quantity = 795** ← inchangée)
- **No grouping** because HS codes are different

### Implementation Files

- `src/item_grouper.py`: Grouping logic and quantity management
- `src/rfcv_parser.py`: Integration into conversion pipeline (line 67-72)
- `tests/test_item_grouping.py`: 9 unit tests (100% pass)

### HS Code Extraction

The HS code used for grouping is extracted from:
- **Section**: "26. Articles"
- **Column**: "Code SH Attesté"
- **Format**: `XXXX.XX.XX.XX` → cleaned to `XXXXXXXX` (8 digits)
- **Storage**: `item.tarification.hscode.commodity_code`

### Logging

The system provides detailed grouping information:

**With Grouping (Same HS Codes)**:
```
INFO: Regroupement d'articles : 2 avec châssis, 33 sans châssis
INFO: Regroupement en 2 groupes par code HS
INFO: Regroupement effectif détecté → application des règles de quantité
INFO:   Groupe HS 87042110 (PREMIER): 10 articles → 1 article (quantité = 35)
INFO:   Groupe HS 87112090: 23 articles → 1 article (quantité = 0)
INFO: Résultat regroupement : 35 articles → 4 articles finaux
```

**No Grouping (Different HS Codes)**:
```
INFO: Regroupement d'articles : 0 avec châssis, 2 sans châssis
INFO: Regroupement en 2 groupes par code HS
INFO: Tous les codes HS sont différents → aucun regroupement nécessaire
INFO: Résultat : 2 articles → 2 articles (inchangé)
```

### Benefits

- **Simplified declarations**: Fewer articles to process in ASYCUDA
- **Compliance**: Vehicles with chassis remain individually tracked
- **Accuracy**: Total package count preserved from official RFCV section 24
- **Transparency**: Full logging of grouping decisions

## Insurance Calculation (Assurance)

The system calculates insurance (assurance) using a customs-mandated formula that requires a variable exchange rate provided by the user before each conversion.

### Calculation Formula

**Formula**: `ceiling(2500 + (FOB + FRET) × TAUX × 0.15%)`

Where:
- **FOB**: Total FOB value from section "19. Total Valeur FOB attestée"
- **FRET**: Freight value from section "20. Fret Attesté"
- **TAUX**: Customs exchange rate (communicated by customs, variable, 4 decimals)
- **ceiling()**: Round up to the nearest integer (ensures integer XOF amount)
- **Result**: Always in XOF (Franc CFA) with rate 1.0

**Important**: The insurance amount is rounded UP (ceiling) before proportional distribution to ensure an integer value. The proportional distribution then uses the Largest Remainder Method to guarantee that the sum of article insurances equals exactly the total insurance amount.

### Required Parameter: `taux_douane`

**ALL conversions** require the `taux_douane` parameter (customs exchange rate):

**Format Requirements**:
- ✅ **Decimal separator**: PERIOD (`.`) - international format
- ❌ **Comma (`,`)**: NOT ACCEPTED - will cause validation error
- ✅ **Valid examples**: `573.139`, `573.14`, `573` (becomes 573.0)
- ❌ **Invalid examples**: `573,139`, `573,14` (comma causes error)
- ℹ️ **Trailing zeros**: Not required (`573.139` equals `573.1390`)

**CLI Usage**:
```bash
# Single file conversion - CORRECT (period)
python converter.py "DOSSIER 18236.pdf" --taux-douane 573.139 -v    # ✅

# Single file conversion - INCORRECT (comma)
# python converter.py "DOSSIER 18236.pdf" --taux-douane 573,139 -v  # ❌ ERROR

# Batch processing
python converter.py -d tests/ --batch --taux-douane 573.139 --workers 4
```

**API Usage**:
```bash
# Synchronous conversion - CORRECT (period)
curl -X POST "http://localhost:8000/api/v1/convert" \
  -F "file=@DOSSIER.pdf" \
  -F "taux_douane=573.139"    # ✅ Period

# Synchronous conversion - INCORRECT (comma)
# curl -X POST "http://localhost:8000/api/v1/convert" \
#   -F "file=@DOSSIER.pdf" \
#   -F "taux_douane=573,139"  # ❌ Comma = 422 Validation Error

# Asynchronous conversion
curl -X POST "http://localhost:8000/api/v1/convert/async" \
  -F "file=@DOSSIER.pdf" \
  -F "taux_douane=573.139"

# Batch conversion with per-file rates (period required in JSON list)
curl -X POST "http://localhost:8000/api/v1/batch" \
  -F "files=@DOSSIER1.pdf" \
  -F "files=@DOSSIER2.pdf" \
  -F "taux_douanes=[573.139, 580.25]"    # ✅ Periods in JSON
```

### Null Handling

Insurance is set to `null` when:
- FOB value is missing, zero, or invalid
- FRET value is missing, zero, or invalid
- `taux_douane` parameter is not provided
- All linked fields (proportional distribution) are also set to null

### Implementation

**Core Files**:
- `src/rfcv_parser.py`: Extracts FOB/FRET, calculates insurance (lines 567-594)
- `src/proportional_calculator.py`: Handles `insurance=None` gracefully
- `converter.py`: CLI validation requires `--taux-douane`
- `src/api/routes/convert.py`: Form parameter `taux_douane` required
- `src/api/routes/batch.py`: JSON list of taux (one per file)
- `src/batch_processor.py`: Per-file taux support in BatchConfig

**Calculation Logic** (rfcv_parser.py:567-594):
```python
# Section 21: Assurance - CALCUL selon nouvelle formule douanière
if fob and fret_str and self.taux_douane:
    fob_value = self._parse_number(fob)
    fret_value = self._parse_number(fret_str)

    if fob_value is not None and fret_value is not None and fob_value > 0 and fret_value > 0:
        # Formula: 2500 + (FOB + FRET) × TAUX × 0.15%
        assurance_xof = 2500 + (fob_value + fret_value) * self.taux_douane * 0.0015

        valuation.insurance = CurrencyAmount(
            amount_national=assurance_xof,
            amount_foreign=assurance_xof,
            currency_code='XOF',
            currency_name='Franc CFA',
            currency_rate=1.0
        )
    else:
        valuation.insurance = None
else:
    valuation.insurance = None
```

### Test Rate

For testing purposes, use USD rate: **573.139** (4 decimals)

### XML Output

Insurance appears in the `<Valuation>` section:
```xml
<Valuation>
  <Gs_Invoice>
    <Gs_Invoice_fob_value_national>12500000</Gs_Invoice_fob_value_national>
    <Gs_Invoice_freight_national>850000</Gs_Invoice_freight_national>
    <Gs_Invoice_insurance_national>156923.75</Gs_Invoice_insurance_national>
    <Gs_Invoice_insurance_rate>1.0</Gs_Invoice_insurance_rate>
    <Gs_invoice_insurance_currency>XOF</Gs_invoice_insurance_currency>
  </Gs_Invoice>
</Valuation>
```

When null:
```xml
<Gs_Invoice_insurance_national><null/></Gs_Invoice_insurance_national>
```

## Payment Report (Rapport de Paiement)

The system supports an optional payment report number (Treasury receipt number) that can be provided when converting RFCV to XML ASYCUDA.

### What is the Payment Report?

**Payment Report** (`Deffered_payment_reference` in ASYCUDA) is the Treasury receipt number (numéro de quittance du Trésor Public) generated AFTER payment of customs duties and taxes.

**Format**: `[Year][Type][Sequence][Letter]`

**Example**: `25P2003J`
- `25`: Year 2025
- `P`: Type (P = Payment)
- `2003`: Sequential number
- `J`: Control letter

### Customs Clearance Workflow

1. **RFCV issued** → Inspection document (BEFORE clearance)
2. **RFCV → XML conversion** → Our system (payment report optional)
3. **Taxes calculation** → ASYCUDA system
4. **Payment to Treasury** → Receipt number generated (e.g., 25P2003J)
5. **Entry in ASYCUDA** → Fill `Deffered_payment_reference`
6. **Clearance granted** → Goods can leave port

### Optional Parameter: `rapport_paiement`

The `rapport_paiement` parameter is **OPTIONAL** because:
- Payment report is generated AFTER tax payment
- RFCV is issued BEFORE customs clearance
- Number can be added manually in ASYCUDA after payment

**When to Provide**:
- ✅ If you already have the Treasury receipt number
- ✅ When converting post-payment RFCV for archival purposes
- ❌ Not available during initial RFCV conversion (most common case)

**CLI Usage**:
```bash
# With payment report (if already available)
python converter.py "DOSSIER 18236.pdf" \
  --taux-douane 573.139 \
  --rapport-paiement 25P2003J \
  -v

# Without payment report (most common - filled later in ASYCUDA)
python converter.py "DOSSIER 18236.pdf" \
  --taux-douane 573.139 \
  -v

# Batch processing with payment report
python converter.py -d tests/ \
  --batch \
  --taux-douane 573.139 \
  --rapport-paiement 25P2003J \
  --workers 4
```

**API Usage**:
```bash
# Synchronous conversion with payment report
curl -X POST "http://localhost:8000/api/v1/convert" \
  -F "file=@DOSSIER.pdf" \
  -F "taux_douane=573.139" \
  -F "rapport_paiement=25P2003J"

# Synchronous conversion without payment report
curl -X POST "http://localhost:8000/api/v1/convert" \
  -F "file=@DOSSIER.pdf" \
  -F "taux_douane=573.139"

# Asynchronous conversion with payment report
curl -X POST "http://localhost:8000/api/v1/convert/async" \
  -F "file=@DOSSIER.pdf" \
  -F "taux_douane=573.139" \
  -F "rapport_paiement=25P2003J"
```

### Empty vs Provided Behavior

**Without parameter** (default):
```xml
<Financial>
  <Deffered_payment_reference/>
  <Mode_of_payment>COMPTE DE PAIEMENT</Mode_of_payment>
</Financial>
```

**With parameter** (`--rapport-paiement 25P2003J`):
```xml
<Financial>
  <Deffered_payment_reference>25P2003J</Deffered_payment_reference>
  <Mode_of_payment>COMPTE DE PAIEMENT</Mode_of_payment>
</Financial>
```

### Implementation

**Core Files**:
- `src/rfcv_parser.py`: Accepts optional `rapport_paiement` parameter (lines 27-38, 428-431)
- `converter.py`: CLI argument `--rapport-paiement` (line 188-193)
- `src/api/routes/convert.py`: Form parameter `rapport_paiement` (sync and async)
- `src/api/services/conversion_service.py`: Service layer parameter passing

**Parser Logic** (rfcv_parser.py:428-431):
```python
# Rapport de paiement (Deffered_payment_reference)
# Fourni en paramètre si disponible (numéro de quittance du Trésor)
if hasattr(self, 'rapport_paiement') and self.rapport_paiement:
    financial.deferred_payment_ref = self.rapport_paiement
```

### Distinction: RFCV Payment Mode ≠ Customs Payment Report

**RFCV Section 10 "Mode de Paiement"**:
- Commercial payment between importer and exporter
- Examples: "Bank transfer", "Documentary credit", "Wire transfer"
- **NOT related** to customs duties payment

**Customs Payment Report** (ASYCUDA `Deffered_payment_reference`):
- Payment of duties and taxes to Treasury
- Values: Treasury receipt numbers like "25P2003J"
- **Different** from commercial RFCV payment mode

### Validation Rules

**No strict validation is applied**:
- Format responsibility: User must provide valid Treasury receipt number
- Length: Typically 8 characters (e.g., "25P2003J")
- Characters: Alphanumeric
- Case: Usually uppercase

The system accepts any string value without format validation, allowing for variations in Treasury receipt formats.

## Automatic VIN Chassis Generation (v2.1)

The system supports automatic generation of VIN ISO 3779 chassis numbers (17 characters with checksum) during RFCV to XML conversion.

### What is VIN Chassis Generation?

**VIN ISO 3779 Generation** allows creating unique Vehicle Identification Numbers compliant with ISO 3779 standard:
- **Format**: 17 characters (no I, O, Q)
- **Structure**: WMI (3) + VDS (5) + Year (1) + Plant (1) + Checksum (1) + Sequence (6)
- **Uniqueness**: Persistent sequences guarantee no duplicates across conversions
- **Thread-safe**: Concurrent generation supported

**Example VIN**: `LZSHCKZS0SS000001`
- `LZS`: World Manufacturer Identifier (WMI)
- `HCKZS`: Vehicle Descriptor Section (VDS)
- `0`: Checksum digit
- `S`: Year 2025 (ISO 3779 code)
- `S`: Plant code
- `000001`: Sequential number

### Required Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `--generate-chassis` | flag | ✅ Yes | - | Activate automatic generation |
| `--chassis-quantity` | integer | ✅ Yes | - | Number of VIN to generate |
| `--chassis-wmi` | string(3) | ✅ Yes | - | World Manufacturer Identifier (ex: LZS, LFV) |
| `--chassis-year` | integer | ✅ Yes | - | Manufacturing year (1980-2055) |
| `--chassis-vds` | string(5) | ❌ No | HCKZS | Vehicle Descriptor Section |
| `--chassis-plant-code` | string(1) | ❌ No | S | Plant manufacturing code |

### CLI Usage

**Basic generation** (180 chassis with LZS/2025):
```bash
python converter.py "DOSSIER_18236.pdf" \
  --taux-douane 573.139 \
  --generate-chassis \
  --chassis-quantity 180 \
  --chassis-wmi LZS \
  --chassis-year 2025 \
  -v
```

**Complete generation** (50 chassis with LFV/2024):
```bash
python converter.py "DOSSIER_18237.pdf" \
  --taux-douane 573.139 \
  --generate-chassis \
  --chassis-quantity 50 \
  --chassis-wmi LFV \
  --chassis-year 2024 \
  --chassis-vds BA01A \
  --chassis-plant-code S \
  -v
```

**Batch processing** (first file gets config in CLI mode):
```bash
python converter.py RFCV-CHASSIS/FCVR-191.pdf RFCV-CHASSIS/FCVR-193.pdf \
  --batch \
  --taux-douane 573.139 \
  --generate-chassis \
  --chassis-quantity 75 \
  --chassis-wmi LFV \
  --chassis-year 2024 \
  --workers 2 \
  -o output/batch_test \
  -v
```

**Note**: In CLI batch mode, only the first file receives the chassis configuration. For individual configuration per file, use the API batch endpoint.

### API Usage

**Synchronous conversion with chassis generation**:
```bash
curl -X POST "http://localhost:8000/api/v1/convert" \
  -H "X-API-Key: votre_cle_api" \
  -F "file=@DOSSIER_18236.pdf" \
  -F "taux_douane=573.139" \
  -F 'chassis_config={"generate_chassis":true,"quantity":180,"wmi":"LZS","year":2025}'
```

**Asynchronous conversion with chassis generation**:
```bash
curl -X POST "http://localhost:8000/api/v1/convert/async" \
  -H "X-API-Key: votre_cle_api" \
  -F "file=@DOSSIER_18237.pdf" \
  -F "taux_douane=573.139" \
  -F 'chassis_config={"generate_chassis":true,"quantity":50,"wmi":"LFV","year":2024,"vds":"BA01A"}'
```

**Batch conversion with individual configs**:
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

**Result**:
- File 1: 180 VIN generated (LZS/2025)
- File 2: 50 VIN generated (LFV/2024)
- File 3: Automatic detection (no generation)

### JSON Configuration Format

**Minimal configuration**:
```json
{
  "generate_chassis": true,
  "quantity": 180,
  "wmi": "LZS",
  "year": 2025
}
```

**Complete configuration**:
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

### XML Output Format

For each vehicle with generated VIN, the XML contains:

```xml
<Item>
  <!-- Chassis document (code 6122) -->
  <Attached_documents>
    <Attached_document_code>6122</Attached_document_code>
    <Attached_document_name>CHASSIS MOTOS</Attached_document_name>
    <Attached_document_reference>LZSHCKZS0SS000001</Attached_document_reference>
    <Attached_document_from_rule>1</Attached_document_from_rule>
  </Attached_documents>

  <!-- Chassis in Marks2 with CH: prefix -->
  <Packages>
    <Marks1_of_packages>TRICYCLE AP150ZK LZSHCKZS2S8054073</Marks1_of_packages>
    <Marks2_of_packages>CH: LZSHCKZS0SS000001</Marks2_of_packages>
  </Packages>

  <!-- Preserved description (original data intact) -->
  <Goods_description>
    <Country_of_origin_code>CN</Country_of_origin_code>
    <Description_of_goods>TRICYCLE AP150ZK LZSHCKZS2S8054073</Description_of_goods>
  </Goods_description>
</Item>
```

**Key points**:
- ✅ All original RFCV section 26 data preserved
- ✅ Old chassis remains in description and Marks1
- ✅ New VIN added separately in document 6122 and Marks2
- ✅ Double traceability: old + new chassis

### Sequence Persistence

VIN sequences are persisted in `data/chassis_sequences.json`:

```json
{
  "LZSHCKZSS": 240,
  "LFVHCKZSR": 75
}
```

**Key**: `WMI + VDS + Year + Plant` (e.g., "LZSHCKZSS" = LZS + HCKZS + S for 2025)
**Value**: Last sequence number used

**Thread-safety**: Uses `threading.Lock()` for concurrent access

### Implementation Files

**Core Integration**:
- `src/rfcv_parser.py`: Constructor accepts `chassis_config`, generation logic (lines 27-69, 689-882)
- `converter.py`: CLI arguments and validation (lines 214-308, 327-388)
- `src/batch_processor.py`: BatchConfig with `chassis_configs` list (line 48, 109-136)

**API Layer**:
- `src/api/routes/convert.py`: Sync/async endpoints with JSON parsing (lines 39-97, 217-246)
- `src/api/routes/batch.py`: Batch endpoint with configs list (lines 56-99)
- `src/api/services/conversion_service.py`: Service layer parameter passing
- `src/api/services/batch_service.py`: Batch service with chassis_configs support

**Data Models**:
- `src/api/models/api_models.py`: ChassisConfig Pydantic model with validation

### Testing

**Manual CLI Tests**: See `claudedocs/chassis_generation_tests.md`
- Test 1: FCVR-189.pdf (180 chassis generated)
- Test 2: FCVR-190.pdf (50 chassis with limitation)
- Test 3: FCVR-194.pdf (10 chassis with sequence continuity)
- Test 4: Batch mode (2 files, 2 workers, different WMI/year)

**Automated Tests**: 198/198 tests passed (0 regression)

**API Documentation**: See `claudedocs/api_chassis_generation.md`
- Complete API reference with examples
- Error handling and troubleshooting
- Code examples (Python, JavaScript)

**Swagger UI**: http://localhost:8000/docs
- Interactive documentation with chassis examples
- Try-it-out functionality with pre-filled configs

### Limitations and Behavior

**Generation Limitation**:
- System generates exactly `quantity` VIN numbers
- Articles beyond the limit receive no chassis
- Warning logged when limit reached

**CLI Batch Mode**:
- Only the first file receives chassis configuration
- Other files use automatic detection (existing behavior)
- **Workaround**: Use API batch endpoint for individual configs per file

**Data Preservation**:
- All RFCV section 26 data preserved (HS code, origin, FOB, description)
- Old chassis numbers remain in description
- New VIN added separately (non-destructive)

### Year Codes (ISO 3779)

| Year | Code | Year | Code | Year | Code |
|------|------|------|------|------|------|
| 2024 | R | 2025 | S | 2026 | T |
| 2027 | V | 2028 | W | 2029 | X |
| 2030 | Y | 2031 | 1 | 2032 | 2 |

### Performance

**Overhead**: Negligible (<50ms for 180 VIN)
- VIN calculation: ~0.2ms per chassis
- Checksum computation: Optimized algorithm
- JSON persistence: Lightweight file operations

**Conversion Times** (tested):
- 180 chassis: ~1.2 seconds total
- 50 chassis: ~0.6 seconds total
- Batch 2 files (2 workers): ~1.22 seconds total

## Architecture

### Core Processing Pipeline

The conversion follows a 3-stage pipeline:

1. **PDF Extraction** (`src/pdf_extractor.py`)
   - Uses `pdfplumber` to extract text and tables from PDF
   - Context manager pattern for resource cleanup
   - Methods: `extract_all_text()`, `extract_all_tables()`, `get_page_count()`

2. **RFCV Parsing** (`src/rfcv_parser.py`)
   - Parses extracted data into structured `RFCVData` dataclass
   - Handles Unicode apostrophes (ASCII `'` and Unicode `'` U+2019)
   - Critical for extracting trader names correctly

3. **XML Generation** (`src/xml_generator.py`)
   - Generates ASYCUDA-compliant XML from `RFCVData`
   - Uses `<null/>` convention for empty fields (ASYCUDA standard)
   - Methods: `generate()`, `save(path, pretty_print=True)`

### Data Models (`src/models.py`)

15+ dataclasses representing ASYCUDA structure:
- `RFCVData`: Root container with all sections
- `Identification`, `Trader`, `Country`, `TransportInfo`
- `Financial`, `Valuation`, `Container`, `Item`
- Nested structures: `HSCode`, `Tarification`, `Taxation`, `Package`

Key: All models use `Optional` fields and `field(default_factory=list)` for lists.

### API Architecture (`src/api/`)

FastAPI application with service-oriented architecture:

```
src/api/
├── main.py              # FastAPI app, CORS, lifespan events
├── core/                # Configuration and dependencies
│   ├── config.py        # Pydantic settings (env vars with API_ prefix)
│   ├── dependencies.py  # Startup tasks, directory creation
│   └── background.py    # Task manager, periodic cleanup
├── routes/              # API endpoints (4 routers)
│   ├── convert.py       # Conversion endpoints (sync/async)
│   ├── batch.py         # Batch processing endpoints
│   ├── files.py         # File download endpoints
│   └── health.py        # Health check and metrics
├── services/            # Business logic wrappers
│   ├── conversion_service.py
│   ├── batch_service.py
│   ├── job_service.py
│   └── storage_service.py
└── models/
    └── api_models.py    # Pydantic request/response models
```

**Important**: The API wraps core converter logic (`RFCVParser` + `XMLGenerator`) in service layer. Never bypass services to call core directly from routes.

### Background Processing

- `src/api/core/background.py`: `TaskManager` handles async jobs
- Job storage: In-memory dicts (`jobs`, `batch_jobs`) indexed by UUID
- Periodic cleanup: Runs every 6 hours (configurable via `API_CLEANUP_INTERVAL_HOURS`)
- Job expiry: 24 hours default (`API_JOB_EXPIRY_HOURS`)

### Batch Processing (`src/batch_processor.py`)

- Uses `multiprocessing` for parallel conversion
- `BatchConfig` dataclass for configuration
- `BatchProcessor.process()` returns dict with results
- `BatchReportGenerator` (`src/batch_report.py`) creates JSON/CSV/Markdown reports

## Environment Configuration

API settings via environment variables (prefix: `API_`):

```bash
API_HOST=0.0.0.0
API_PORT=8000
API_DEBUG=False
API_UPLOAD_DIR=uploads
API_OUTPUT_DIR=output
API_MAX_UPLOAD_SIZE=52428800  # 50MB in bytes
API_DEFAULT_WORKERS=4
API_MAX_WORKERS=8
API_JOB_EXPIRY_HOURS=24
```

Configuration loads from `.env` file (see `.env.example`). Settings class in `src/api/core/config.py` uses `pydantic-settings` v2.

## Testing Architecture

### API Tests (`tests/api/`)

- Uses `pytest` with `pytest-asyncio` for async tests
- `conftest.py` provides fixtures: `app`, `client`, `test_pdf_path`
- `httpx.AsyncClient` for async API testing
- Test files: `test_convert.py`, `test_batch.py`, `test_files.py`, `test_health.py`

### Converter Tests (`tests/test_converter.py`)

- `ConverterTester` class with batch testing capability
- `MetricsCollector` tracks conversion quality metrics
- Generates reports via `scripts/generate_report.py`
- Run with `-d tests/ -v` for verbose output

## Key Patterns & Conventions

### Path Handling

Always use `sys.path.insert(0, str(Path(__file__).parent / 'src'))` at top of scripts to ensure imports work from `src/` directory.

### Error Handling

- API: Return structured JSON errors with `error` and `detail` fields
- CLI: Print to stderr and exit with code 1 on failure
- Batch: `continue_on_error=True` by default, collect all errors

### Metrics System

`src/metrics.py` provides:
- `ConversionMetrics`: Individual conversion metrics
- `MetricsCollector`: Aggregates metrics, calculates fill rates
- Fill rate: Percentage of non-null fields across all dataclass attributes

### Unicode Handling

RFCV parsing handles both ASCII (`'`) and Unicode (`'` U+2019) apostrophes. Critical for trader name extraction. See `src/rfcv_parser.py` patterns.

## CI/CD

GitHub Actions workflows in `.github/workflows/`:
- `test.yml`: Runs pytest and ruff linter on push/PR
- `docker.yml`: Builds and pushes Docker images to GHCR
- `release.yml`: Creates releases on version tags
- `deploy-render.yml`: Auto-deploy to Render on main/tags

## Deployment

- **Render**: Configured via `render.yaml`, auto-deploys from `ghcr.io` images
- **Docker**: Multi-stage build, non-root user (appuser), health checks
- **API URL patterns**: `/api/v1/{endpoint}` for all endpoints

## Important Notes

1. **XML Format**: Always use `<null/>` for empty fields (ASYCUDA standard)
2. **CORS**: Configured to allow all origins (`["*"]`) for API
3. **File uploads**: Use `python-multipart` for FastAPI file handling
4. **Async patterns**: Background tasks use `asyncio.create_task()` in lifespan
5. **Worker limits**: Batch processing capped at `API_MAX_WORKERS` (default 8)

## API Endpoints Reference

**Conversion**: `POST /api/v1/convert` (sync), `POST /api/v1/convert/async` (async)
**Status**: `GET /api/v1/convert/{job_id}`
**Results**: `GET /api/v1/convert/{job_id}/result`
**Download**: `GET /api/v1/convert/{job_id}/download`
**Batch**: `POST /api/v1/batch` (multipart upload)
**Batch Status**: `GET /api/v1/batch/{batch_id}/status`
**Health**: `GET /api/v1/health`
**Metrics**: `GET /api/v1/metrics`, `GET /api/v1/metrics/{job_id}`

Documentation available at `/docs` (Swagger) and `/redoc` when API is running.
