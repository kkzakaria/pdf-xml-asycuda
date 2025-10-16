# Tests API

Suite de tests pour l'API REST FastAPI du convertisseur PDF RFCV → XML ASYCUDA.

## Structure des tests

```
tests/api/
├── conftest.py              # Fixtures pytest communes
├── test_health.py           # Tests health check et métriques
├── test_convert.py          # Tests endpoints conversion
├── test_batch.py            # Tests endpoints batch
├── test_files.py            # Tests endpoints files
└── README.md                # Ce fichier
```

## Exécution des tests

### Tous les tests API
```bash
pytest tests/api/ -v
```

### Tests spécifiques
```bash
# Health endpoints uniquement
pytest tests/api/test_health.py -v

# Conversion endpoints
pytest tests/api/test_convert.py -v

# Batch endpoints
pytest tests/api/test_batch.py -v

# Files endpoints
pytest tests/api/test_files.py -v
```

### Avec couverture
```bash
pytest tests/api/ --cov=src/api --cov-report=html
```

## Résultats

**Total: 26 tests**
- ✅ 26 tests passés (100%)
- ⏭️  0 tests skippés
- ❌ 0 échecs

### Tests par module

**test_health.py** (4 tests) - ✅ 100% passés
- `test_health_check` - ✅ Health check endpoint
- `test_root_endpoint` - ✅ Endpoint racine
- `test_metrics_endpoint` - ✅ Métriques système
- `test_openapi_docs` - ✅ Documentation OpenAPI

**test_convert.py** (9 tests) - ✅ 100% passés
- `test_convert_sync_success` - ✅ Conversion synchrone
- `test_convert_sync_no_file` - ✅ Validation sans fichier
- `test_convert_sync_invalid_file` - ✅ Fichier invalide
- `test_convert_async_success` - ✅ Conversion async
- `test_get_job_status_not_found` - ✅ Job inexistant
- `test_get_job_result_success` - ✅ Résultat job
- `test_download_xml_success` - ✅ Download XML
- `test_download_xml_not_found` - ✅ XML inexistant
- `test_concurrent_conversions` - ✅ Conversions concurrentes

**test_batch.py** (8 tests) - ✅ 100% passés
- `test_batch_convert_success` - ✅ Batch conversion réussie
- `test_batch_convert_no_files` - ✅ Validation sans fichiers
- `test_batch_status` - ✅ Status du batch
- `test_batch_status_not_found` - ✅ Batch inexistant
- `test_batch_results` - ✅ Résultats batch
- `test_batch_report` - ✅ Rapport batch
- `test_batch_workers_validation` - ✅ Validation workers
- `test_batch_progress_tracking` - ✅ Suivi progression

**test_files.py** (5 tests) - ✅ 100% passés
- `test_download_xml_by_id` - ✅ Download par ID
- `test_download_xml_not_found` - ✅ Fichier inexistant
- `test_file_metadata` - ✅ Métadonnées
- `test_file_metadata_not_found` - ✅ Métadonnées inexistantes
- `test_download_with_extension` - ✅ Download avec extension

## Fixtures disponibles

### `client` (async)
Client HTTP async pour tester l'API
```python
async def test_example(client):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
```

### `sample_pdf`
Retourne le chemin vers un PDF de test (skip si indisponible)
```python
def test_convert(client, sample_pdf):
    with open(sample_pdf, "rb") as f:
        files = {"file": (sample_pdf.name, f, "application/pdf")}
        response = await client.post("/api/v1/convert", files=files)
```

### `multiple_pdfs`
Liste de PDFs pour tests batch (skip si < 2 PDFs)
```python
def test_batch(client, multiple_pdfs):
    files = [(pdf.name, open(pdf, "rb")) for pdf in multiple_pdfs]
    response = await client.post("/api/v1/batch", files=files)
```

## Coverage

Les tests couvrent:
- ✅ Tous les endpoints health/metrics
- ✅ Validation des requêtes
- ✅ Gestion d'erreurs (404, 422, 500)
- ✅ Background tasks (batch)
- ✅ Job tracking
- ✅ Documentation OpenAPI
- ✅ Conversions réelles (sync et async)
- ✅ Téléchargement et métadonnées de fichiers
- ✅ Conversions concurrentes

## Dépendances

```txt
pytest>=8.0.0
pytest-asyncio>=0.23.0
httpx>=0.27.0
```

## Notes

- Les tests utilisent les fichiers PDF disponibles dans `tests/` (7 PDFs de test)
- Les tests utilisent des dossiers temporaires (`test_uploads`, `test_output`)
- Cleanup automatique après chaque test
- Tests asynchrones avec `@pytest.mark.asyncio`
- Tous les tests passent avec une couverture complète des 13 endpoints
