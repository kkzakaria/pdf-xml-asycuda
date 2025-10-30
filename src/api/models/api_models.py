"""
Modèles Pydantic pour l'API
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime
from enum import Enum


class JobStatus(str, Enum):
    """Status d'un job de conversion"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ReportFormat(str, Enum):
    """Formats de rapport disponibles"""
    JSON = "json"
    CSV = "csv"
    MARKDOWN = "md"


# ============= Request Models =============

class ConvertRequest(BaseModel):
    """Requête de conversion (pour async avec metadata)"""
    filename: str
    taux_douane: float = Field(..., gt=0, description="Taux de change douanier pour calcul assurance (format: 573.1390)")
    verbose: bool = False


class BatchConvertRequest(BaseModel):
    """Requête de conversion batch"""
    taux_douane: float = Field(..., gt=0, description="Taux de change douanier global pour tous les fichiers (format: 573.1390)")
    recursive: bool = False
    pattern: str = "*.pdf"
    workers: int = Field(default=4, ge=1, le=8)
    verbose: bool = False

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "taux_douane": 573.1390,
            "recursive": False,
            "pattern": "*.pdf",
            "workers": 4,
            "verbose": False
        }
    })


# ============= Response Models =============

class ConversionMetrics(BaseModel):
    """Métriques d'une conversion"""
    items_count: int
    containers_count: int
    fill_rate: float
    warnings_count: int
    warnings: List[str]
    xml_valid: bool
    has_exporter: bool
    has_consignee: bool
    processing_time: float

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "items_count": 12,
            "containers_count": 2,
            "fill_rate": 68.5,
            "warnings_count": 0,
            "warnings": [],
            "xml_valid": True,
            "has_exporter": True,
            "has_consignee": True,
            "processing_time": 0.64
        }
    })


class ConvertResponse(BaseModel):
    """Réponse de conversion synchrone"""
    success: bool
    job_id: str
    filename: str
    output_file: Optional[str] = None
    message: str
    metrics: Optional[ConversionMetrics] = None
    processing_time: float

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "success": True,
            "job_id": "conv_abc123xyz",
            "filename": "DOSSIER_18236.pdf",
            "output_file": "DOSSIER_18236.xml",
            "message": "Conversion réussie",
            "metrics": {
                "items_count": 12,
                "containers_count": 2,
                "fill_rate": 68.5,
                "warnings_count": 0,
                "warnings": [],
                "xml_valid": True,
                "has_exporter": True,
                "has_consignee": True,
                "processing_time": 0.64
            },
            "processing_time": 0.64
        }
    })


class ConvertAsyncResponse(BaseModel):
    """Réponse de conversion asynchrone"""
    job_id: str
    status: JobStatus
    message: str
    created_at: datetime

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "job_id": "conv_abc123xyz",
            "status": "pending",
            "message": "Conversion en cours",
            "created_at": "2025-01-15T10:30:00Z"
        }
    })


class JobStatusResponse(BaseModel):
    """Réponse de status de job"""
    job_id: str
    status: JobStatus
    filename: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    progress: Optional[int] = None  # 0-100
    message: str
    error: Optional[str] = None

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "job_id": "conv_abc123xyz",
            "status": "completed",
            "filename": "DOSSIER_18236.pdf",
            "created_at": "2025-01-15T10:30:00Z",
            "completed_at": "2025-01-15T10:30:45Z",
            "progress": 100,
            "message": "Conversion terminée",
            "error": None
        }
    })


class BatchJobResponse(BaseModel):
    """Réponse de job batch"""
    batch_id: str
    status: JobStatus
    total_files: int
    processed: int
    successful: int
    failed: int
    created_at: datetime
    completed_at: Optional[datetime] = None
    message: str

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "batch_id": "batch_xyz789abc",
            "status": "processing",
            "total_files": 7,
            "processed": 4,
            "successful": 4,
            "failed": 0,
            "created_at": "2025-01-15T10:30:00Z",
            "completed_at": None,
            "message": "Traitement en cours: 4/7 fichiers"
        }
    })


class BatchFileResult(BaseModel):
    """Résultat d'un fichier dans un batch"""
    filename: str
    success: bool
    output_file: Optional[str] = None
    processing_time: float
    error: Optional[str] = None
    metrics: Optional[ConversionMetrics] = None


class BatchResultsResponse(BaseModel):
    """Résultats détaillés d'un batch"""
    batch_id: str
    status: JobStatus
    total_files: int
    successful: int
    failed: int
    total_time: float
    results: List[BatchFileResult]

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "batch_id": "batch_xyz789abc",
            "status": "completed",
            "total_files": 7,
            "successful": 7,
            "failed": 0,
            "total_time": 3.64,
            "results": [
                {
                    "filename": "DOSSIER_18236.pdf",
                    "success": True,
                    "output_file": "DOSSIER_18236.xml",
                    "processing_time": 0.64,
                    "error": None,
                    "metrics": {}
                }
            ]
        }
    })


class FileMetadataResponse(BaseModel):
    """Métadonnées d'un fichier"""
    file_id: str
    filename: str
    size_bytes: int
    created_at: datetime
    mime_type: str
    is_available: bool

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "file_id": "file_abc123",
            "filename": "DOSSIER_18236.xml",
            "size_bytes": 15360,
            "created_at": "2025-01-15T10:30:45Z",
            "mime_type": "application/xml",
            "is_available": True
        }
    })


class MetricsResponse(BaseModel):
    """Métriques système"""
    total_conversions: int
    successful: int
    failed: int
    success_rate: float
    avg_processing_time: float
    avg_fill_rate: float
    total_items: int
    total_containers: int

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "total_conversions": 42,
            "successful": 40,
            "failed": 2,
            "success_rate": 95.2,
            "avg_processing_time": 0.65,
            "avg_fill_rate": 68.5,
            "total_items": 504,
            "total_containers": 84
        }
    })


class HealthResponse(BaseModel):
    """Réponse health check"""
    status: str
    version: str
    uptime_seconds: float
    total_jobs: int

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "status": "healthy",
            "version": "1.0.0",
            "uptime_seconds": 3600.5,
            "total_jobs": 42
        }
    })


class ErrorResponse(BaseModel):
    """Réponse d'erreur standard"""
    error: str
    detail: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "error": "Conversion failed",
            "detail": "Invalid PDF structure",
            "timestamp": "2025-01-15T10:30:45Z"
        }
    })
