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
