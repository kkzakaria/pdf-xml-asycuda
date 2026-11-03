# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PDF RFCV → XML ASYCUDA Converter: A Python-based automation tool that extracts structured data from RFCV (Rapport Final de Contrôle et de Vérification) PDF documents and generates XML files compatible with the ASYCUDA customs system used in Côte d'Ivoire.

## Development Commands

### Testing

```bash
# Run API tests with pytest
python -m pytest tests/api/ -v

# Run specific test file
python -m pytest tests/api/test_convert.py -v

# Run converter tests (generates reports)
python tests/test_converter.py -d tests/ -v

# Run tests without reports
python tests/test_converter.py -d tests/ --no-report

# Run specific feature tests
python -m pytest tests/test_chassis_detection.py -v
python -m pytest tests/test_item_grouping.py -v
```

### Running the Application

```bash
# Start FastAPI server (development)
python run_api.py

# Start with uvicorn directly
python3 -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# CLI conversion - single file (taux_douane required)
python converter.py "DOSSIER 18236.pdf" --taux-douane 573.139 -v

# CLI batch processing
python converter.py -d tests/ --batch --workers 4 --taux-douane 573.139

# CLI with chassis generation
python converter.py "DOSSIER.pdf" --taux-douane 573.139 \
  --generate-chassis --chassis-quantity 180 --chassis-wmi LZS --chassis-year 2025

# Standalone VIN generation (no PDF required)
python vin_generator_cli.py -n 180 -w LZS -y 2025                    # JSON output
python vin_generator_cli.py -n 100 -w LFV -y 2026 --format csv -o vins.csv  # CSV file
python vin_generator_cli.py -n 50 -w ABC -y 2025 --format text       # Text output
```

### Docker

```bash
docker build -t pdf-xml-asycuda .
docker run -p 8000:8000 pdf-xml-asycuda
docker-compose up -d
```

### Linting

```bash
ruff check src/ --output-format=github
```

## Architecture

### Core Processing Pipeline (3 stages)

1. **PDF Extraction** (`src/pdf_extractor.py`) - Uses pdfplumber to extract text/tables
2. **RFCV Parsing** (`src/rfcv_parser.py`) - Parses into `RFCVData` dataclass
3. **XML Generation** (`src/xml_generator.py`) - Generates ASYCUDA-compliant XML

### Key Source Files

| File | Purpose |
|------|---------|
| `src/models.py` | 15+ dataclasses for ASYCUDA structure (`RFCVData`, `Trader`, `Item`, etc.) |
| `src/rfcv_format_2026.py` | Pure-text reader for the current RFCV format (header + items) |
| `src/asycuda_enrichment.py` | Computed ASYCUDA fields after proportional split (CIF, packages, `Value_item`, totals) |
| `src/company_profile.py` | Company profile (`profils/*.ini`) + dossier data applied to `RFCVData` |
| `src/hs_code_rules.py` | HS codes requiring chassis (8701-8716), document code logic |
| `src/item_grouper.py` | Groups articles by HS code for customs declarations |
| `src/proportional_calculator.py` | Distributes values proportionally using Largest Remainder Method |
| `src/chassis_generator.py` | VIN ISO 3779 generation with checksum |
| `src/chassis_sequence_manager.py` | Thread-safe sequence persistence in `data/chassis_sequences.json` |
| `src/batch_processor.py` | Multiprocessing for parallel conversions |
| `src/batch_report.py` | JSON/CSV/Markdown report generation |
| `src/metrics.py` | Conversion quality metrics and fill rate calculation |
| `vin_generator_cli.py` | Standalone CLI for VIN generation (no PDF required) |

### API Architecture (`src/api/`)

```
src/api/
├── main.py              # FastAPI app, CORS, lifespan
├── core/
│   ├── config.py        # Pydantic settings (API_ prefix env vars)
│   ├── background.py    # TaskManager for async jobs
│   ├── dependencies.py  # Startup tasks
│   └── declaration_options.py # Form fields profil/dossier/manifeste/assurance (Depends)
├── routes/              # Routers: convert, batch, files, health, chassis, stats, profiles
│   └── chassis.py       # VIN generation endpoints (standalone)
├── services/            # Business logic wrappers (never bypass)
│   └── chassis_service.py # VIN generation service
└── models/api_models.py # Pydantic request/response models
```

**Important**: Routes must call services, never core converter directly.

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/convert` | POST | Sync conversion |
| `/api/v1/convert/async` | POST | Async conversion (returns job_id) |
| `/api/v1/convert/{job_id}` | GET | Job status |
| `/api/v1/convert/{job_id}/download` | GET | Download XML |
| `/api/v1/batch` | POST | Batch processing |
| `/api/v1/batch/{batch_id}/status` | GET | Batch status |
| `/api/v1/health` | GET | Health check |
| `/api/v1/chassis/generate` | POST | Generate VINs (form-data) |
| `/api/v1/chassis/generate/json` | POST | Generate VINs (JSON body) |
| `/api/v1/chassis/sequences` | GET | VIN sequences status |
| `/api/v1/profils` | GET | Available company profiles |

Documentation at `/docs` (Swagger) and `/redoc`.

## Key Business Rules

### Required Parameter: `taux_douane`

ALL conversions require customs exchange rate:
- **Format**: Period decimal (`.`) - `573.139` not `573,139`
- **CLI**: `--taux-douane 573.139`
- **API**: Form field `taux_douane=573.139`

`taux_douane` is also the **conversion rate to XOF** for the 2026 format (ASYCUDA uses the customs
rate, not the RFCV rate in box 17). XOF RFCVs use rate 1.

### RFCV Formats

`RFCVParser.parse()` detects the format (`rfcv_format_2026.is_format_2026`):
- **Legacy**: `1 234,56`, HS code with dots, long labels — `_parse_format_legacy`
- **2026** (current): `1,234.56`, `19. Total FOB`, article on 3 lines (designation / data / VIN) —
  `_parse_format_2026`
Both build items through `_build_item`, then share `_finalize` (grouping, attached docs,
proportional split, `enrich_for_asycuda`).

### Insurance Calculation

Default (`insurance_mode="formule"`, like production declarations):
```
ceiling(2500 + (FOB + FRET) × TAUX × 0.15%)
```
Option `insurance_mode="rfcv"` (CLI `--assurance-rfcv`, API `assurance=rfcv`): RFCV box 21 × customs
rate (falls back to the formula if absent). Result always in XOF.

### Company Profile and Dossier Data

Values not on the RFCV: office, declarant, bank, account, goods location → `profils/*.ini`
(`company_profile.load_profile`, unknown keys rejected). Dossier data: `--dossier` (declarant
reference = `reference_prefixe` + n°), `--manifeste`, `--nationalite-transport`.
API: `profil=<name>` resolved server-side in `API_PROFILES_DIR` (never a client path).
`rapport_paiement` keeps priority over the profile `compte`.

### Chassis Detection (HS Codes 87xx)

- **Code 6122**: Motos (HS 8711)
- **Code 6022**: Other vehicles (HS 8701-8705, 8427, 8429, 8716)
- VIN format: 17 chars, no I/O/Q, ISO 3779 compliant
- Chassis in `Attached_documents` + `Marks2_of_packages` with `CH:` prefix

### Attached Documents (v2.7.0+)

Each article includes the following ASYCUDA documents automatically:

| Code | Document | Source |
|------|----------|--------|
| `0007` | FACTURE | `financial.invoice_number` + date |
| `0014` | JUSTIFICATION D'ASSURANCE | `VD` |
| `6603` | BORDEREAU DE SUIVI DE CARGAISON | `VD` |
| `2500` | NUMERO DE LIGNE ARTICLE | `item.rfcv_line_number` |
| `2501` | ATTESTATION DE VERIFICATION | `identification.rfcv_number` |
| `6610` | NUMERO FDI | `identification.fdi_number` + date, **first article only**, `from_rule=0` |
| `6122` | NUMERO DE CHASSIS (motos) | `packages.chassis_number` |
| `6022` | NUMERO DE CHASSIS (vehicles) | `packages.chassis_number` |

Order and `Attached_doc_item`: `0007 0014 6603 2500 2501 6610 6122` (6610 on article 1 only).
Document dates are written `M/D/YY` (`asycuda_enrichment.to_asycuda_date`). These rules come from
real declarations (production 28923/28928/31287, ASYCUDA export 28926).

### Computed ASYCUDA Fields (`asycuda_enrichment.py`)

- `Total_cost_itm` = freight + insurance; `Total_CIF_itm` = `Statistical_value` = FOB + freight + insurance
- `Value_item` = `freight+0+insurance+0-0` (thousands with `,`)
- `Value_details` = `Total_cost` = Σ (freight + insurance)
- Packages spread evenly over chassis articles, remainder to the first ones
- `Summary_declaration` = bill of lading; `Free_text_1` = `CH: <VIN>`

### Article Grouping

Articles without chassis grouped by HS code:
- First article of first group gets `total_packages` quantity
- Other grouped articles get quantity = 0
- Articles with chassis never grouped

### Batch Per-File Values

`BatchConfig` lists (`taux_douanes`, `chassis_configs`, `dossiers`, `manifestes`,
`nationalites_transport`) follow `input_paths` order and are matched **by path**
(`BatchProcessor._file_options`), because `find_pdf_files()` sorts files. A single-value
`taux_douanes`/`chassis_configs` list is applied to all files; dossier data never is.

### XML Conventions

- Empty fields use `<null/>` (ASYCUDA standard)
- All models use `Optional` fields
- Lists use `field(default_factory=list)`

## Environment Configuration

API settings via `.env` file (prefix `API_`):

```bash
API_HOST=0.0.0.0
API_PORT=8000
API_DEBUG=False
API_UPLOAD_DIR=uploads
API_OUTPUT_DIR=output
API_MAX_UPLOAD_SIZE=52428800  # 50MB
API_DEFAULT_WORKERS=4
API_MAX_WORKERS=8
API_JOB_EXPIRY_HOURS=24
API_PROFILES_DIR=profils      # company profiles (*.ini), copied into the Docker image
```

## Chassis Registry Caution

Every conversion of an RFCV with VINs registers them in `data/chassis_registry.db`; a second
conversion of the same RFCV raises `DuplicateChassisError` (HTTP 409) unless `force_reprocess`.
In tests and experiments, pass `registry=ChassisRegistry(tmp_path / "registry.db")` to
`RFCVParser` instead of using the repository database.

## Key Patterns

### Path Handling

Scripts use: `sys.path.insert(0, str(Path(__file__).parent / 'src'))`

### Unicode Handling

RFCV parsing handles both ASCII (`'`) and Unicode (`'` U+2019) apostrophes for trader name extraction.

### Error Handling

- API: JSON with `error` and `detail` fields
- CLI: stderr + exit code 1
- Batch: `continue_on_error=True` default

## CI/CD

GitHub Actions in `.github/workflows/`:
- `test.yml`: pytest + ruff on push/PR
- `docker.yml`: Build/push to GHCR
- `release.yml`: Release on version tags
- `deploy-render.yml`: Auto-deploy to Render

## Testing

- API tests: `tests/api/` with pytest-asyncio, httpx.AsyncClient
- Converter tests: `tests/test_converter.py` with MetricsCollector
- Fixtures in `tests/api/conftest.py`
