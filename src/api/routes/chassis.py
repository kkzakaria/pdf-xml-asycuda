"""
Routes de génération de VINs ISO 3779 indépendante
Génération de VINs sans PDF RFCV requis
"""
from fastapi import APIRouter, HTTPException, status, Form, Depends
from fastapi.responses import PlainTextResponse, Response
from typing import Optional

from ..models.api_models import (
    VINGenerationRequest,
    VINGenerationResponse,
    VINGenerationMetadata,
    VINOutputFormat,
    SequencesStatusResponse,
    SequenceInfo,
    ErrorResponse
)
from ..services.chassis_service import chassis_service
from ..core.security import verify_api_key

router = APIRouter(prefix="/api/v1/chassis", tags=["Chassis/VIN"])


@router.post(
    "/generate",
    response_model=VINGenerationResponse,
    summary="Générer des VINs ISO 3779",
    description="""
Génère des numéros de châssis VIN ISO 3779 de manière indépendante, sans PDF RFCV requis.

## Paramètres requis
- **quantity**: Nombre de VINs à générer (1-10000)
- **wmi**: World Manufacturer Identifier - 3 caractères (ex: LZS pour Chine)
- **year**: Année modèle (2001-2030)

## Paramètres optionnels
- **vds**: Vehicle Descriptor Section - 5 caractères (défaut: HCKZS)
- **plant_code**: Code usine - 1 caractère (défaut: S)
- **output_format**: Format de sortie - json, csv ou text (défaut: json)

## Structure VIN ISO 3779
```
Position:  1-3    4-8    9        10    11     12-17
           ----   -----  ----     ----  -----  ------
           WMI    VDS    Checksum Year  Plant  Séquence
           LZS    HCKZS  2        S     8      054073
```

## Unicité garantie
Les séquences sont persistées dans `data/chassis_sequences.json` pour garantir
qu'aucun VIN n'est généré deux fois, même entre redémarrages de l'application.
""",
    responses={
        200: {"description": "VINs générés avec succès"},
        400: {"model": ErrorResponse, "description": "Paramètres invalides"},
        500: {"model": ErrorResponse, "description": "Erreur interne"}
    }
)
async def generate_vins(
    quantity: int = Form(..., ge=1, le=10000, description="Nombre de VINs à générer"),
    wmi: str = Form(..., min_length=3, max_length=3, description="World Manufacturer Identifier (3 caractères)"),
    year: int = Form(..., ge=2001, le=2030, description="Année modèle (2001-2030)"),
    vds: str = Form(default="HCKZS", min_length=5, max_length=5, description="Vehicle Descriptor Section (5 caractères)"),
    plant_code: str = Form(default="S", min_length=1, max_length=1, description="Code usine (1 caractère)"),
    output_format: VINOutputFormat = Form(default=VINOutputFormat.JSON, description="Format de sortie")
):
    """
    Génère des VINs ISO 3779 indépendamment de tout PDF RFCV.

    Retourne les VINs dans le format demandé (JSON, CSV ou texte).
    """
    try:
        # Générer les VINs
        result = chassis_service.generate_vins(
            quantity=quantity,
            wmi=wmi.upper(),
            vds=vds.upper(),
            year=year,
            plant_code=plant_code.upper()
        )

        # Retourner selon le format demandé
        if output_format == VINOutputFormat.CSV:
            csv_content = chassis_service.export_to_csv(result)
            return Response(
                content=csv_content,
                media_type="text/csv",
                headers={
                    "Content-Disposition": f"attachment; filename=vins_{wmi}_{year}_{quantity}.csv"
                }
            )

        elif output_format == VINOutputFormat.TEXT:
            text_content = chassis_service.export_to_text(result)
            return PlainTextResponse(
                content=text_content,
                headers={
                    "Content-Disposition": f"attachment; filename=vins_{wmi}_{year}_{quantity}.txt"
                }
            )

        else:  # JSON (défaut)
            return VINGenerationResponse(
                success=True,
                vins=result["vins"],
                metadata=VINGenerationMetadata(
                    quantity=result["quantity_generated"],
                    wmi=result["wmi"],
                    vds=result["vds"],
                    year=result["year"],
                    plant_code=result["plant_code"],
                    prefix=result["prefix"],
                    start_sequence=result["start_sequence"],
                    end_sequence=result["end_sequence"],
                    generated_at=result["generated_at"]
                )
            )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la génération des VINs: {str(e)}"
        )


@router.get(
    "/sequences",
    response_model=SequencesStatusResponse,
    summary="État des séquences VIN",
    description="""
Affiche l'état actuel des séquences de génération VIN.

Permet de voir:
- Le nombre total de préfixes utilisés
- Le nombre total de VINs générés
- La séquence actuelle pour chaque préfixe
""",
    dependencies=[Depends(verify_api_key)]
)
async def get_sequences_status():
    """
    Récupère l'état de toutes les séquences de VINs.
    """
    try:
        stats = chassis_service.get_sequences_status()

        sequences = []
        total_vins = 0

        for prefix, seq in stats.get("sequences", {}).items():
            sequences.append(SequenceInfo(
                prefix=prefix,
                current_sequence=seq,
                total_generated=seq
            ))
            total_vins += seq

        return SequencesStatusResponse(
            total_prefixes=len(sequences),
            total_vins_generated=total_vins,
            sequences=sequences
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des séquences: {str(e)}"
        )


@router.post(
    "/generate/json",
    response_model=VINGenerationResponse,
    summary="Générer des VINs (JSON)",
    description="Génère des VINs et retourne directement en JSON. Endpoint simplifié.",
    dependencies=[Depends(verify_api_key)]
)
async def generate_vins_json(request: VINGenerationRequest):
    """
    Génère des VINs avec corps JSON (alternative au form-data).
    """
    try:
        result = chassis_service.generate_vins(
            quantity=request.quantity,
            wmi=request.wmi.upper(),
            vds=request.vds.upper(),
            year=request.year,
            plant_code=request.plant_code.upper()
        )

        return VINGenerationResponse(
            success=True,
            vins=result["vins"],
            metadata=VINGenerationMetadata(
                quantity=result["quantity_generated"],
                wmi=result["wmi"],
                vds=result["vds"],
                year=result["year"],
                plant_code=result["plant_code"],
                prefix=result["prefix"],
                start_sequence=result["start_sequence"],
                end_sequence=result["end_sequence"],
                generated_at=result["generated_at"]
            )
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la génération des VINs: {str(e)}"
        )
