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
