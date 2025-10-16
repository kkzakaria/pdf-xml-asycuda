"""
Service de traitement batch
Wrapper autour de batch_processor
"""
import sys
from pathlib import Path
from typing import Dict, Any, List

# Ajouter src au path pour imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from batch_processor import BatchProcessor, BatchConfig


class BatchService:
    """Service de traitement batch"""

    @staticmethod
    def process_batch(
        input_paths: List[str],
        output_dir: str,
        recursive: bool = False,
        pattern: str = "*.pdf",
        workers: int = 4,
        verbose: bool = False
    ) -> Dict[str, Any]:
        """
        Traite un batch de fichiers PDF

        Args:
            input_paths: Liste des chemins d'entrée (fichiers ou dossiers)
            output_dir: Dossier de sortie
            recursive: Recherche récursive
            pattern: Pattern de fichiers
            workers: Nombre de workers
            verbose: Mode verbeux

        Returns:
            Résultats du batch
        """
        # Créer la configuration
        config = BatchConfig(
            input_paths=input_paths,
            output_dir=output_dir,
            recursive=recursive,
            pattern=pattern,
            workers=workers,
            continue_on_error=True,
            verbose=verbose,
            progress_bar=False  # Désactivé pour l'API
        )

        # Exécuter le batch
        processor = BatchProcessor(config)
        results = processor.process()

        return results

    @staticmethod
    def process_files(
        pdf_files: List[str],
        output_dir: str,
        workers: int = 4,
        verbose: bool = False
    ) -> Dict[str, Any]:
        """
        Traite une liste spécifique de fichiers PDF

        Args:
            pdf_files: Liste des fichiers PDF à traiter
            output_dir: Dossier de sortie
            workers: Nombre de workers
            verbose: Mode verbeux

        Returns:
            Résultats du batch
        """
        return BatchService.process_batch(
            input_paths=pdf_files,
            output_dir=output_dir,
            recursive=False,
            pattern="*.pdf",
            workers=workers,
            verbose=verbose
        )


# Instance globale
batch_service = BatchService()
