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
│   └── dependencies.py  # Startup tasks
├── routes/              # 5 routers: convert, batch, files, health, chassis
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

Documentation at `/docs` (Swagger) and `/redoc`.

## Key Business Rules

### Required Parameter: `taux_douane`

ALL conversions require customs exchange rate:
- **Format**: Period decimal (`.`) - `573.139` not `573,139`
- **CLI**: `--taux-douane 573.139`
- **API**: Form field `taux_douane=573.139`

### Insurance Calculation

```
ceiling(2500 + (FOB + FRET) × TAUX × 0.15%)
```
Result always in XOF. Null if FOB, FRET, or taux missing.

### Chassis Detection (HS Codes 87xx)

- **Code 6122**: Motos (HS 8711)
- **Code 6022**: Other vehicles (HS 8701-8705, 8427, 8429, 8716)
- VIN format: 17 chars, no I/O/Q, ISO 3779 compliant
- Chassis in `Attached_documents` + `Marks2_of_packages` with `CH:` prefix

### Attached Documents (v2.7.0+)

Each article includes the following ASYCUDA documents automatically:

| Code | Document | Source |
|------|----------|--------|
| `0007` | FACTURE | `financial.invoice_number` |
| `0014` | JUSTIFICATION D'ASSURANCE | - |
| `6603` | BORDEREAU DE SUIVI DE CARGAISON | `transport.bill_of_lading` |
| `2500` | NUMERO DE LIGNE ARTICLE | `item.rfcv_line_number` |
| `2501` | ATTESTATION DE VERIFICATION | `identification.rfcv_number` |
| `6122` | NUMERO DE CHASSIS (motos) | `packages.chassis_number` |
| `6022` | NUMERO DE CHASSIS (vehicles) | `packages.chassis_number` |

The `Attached_doc_item` field lists all document codes: `0007 0014 6603 2500 2501 6122`

### Article Grouping

Articles without chassis grouped by HS code:
- First article of first group gets `total_packages` quantity
- Other grouped articles get quantity = 0
- Articles with chassis never grouped

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
```

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
