"""
Module de traitement par lot pour la conversion PDF RFCV → XML ASYCUDA
Supporte le traitement parallèle, la recherche récursive et les rapports détaillés
"""
import sys
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing

try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False
    print("Warning: tqdm not installed. Install with 'pip install tqdm' for progress bars.", file=sys.stderr)

from rfcv_parser import RFCVParser
from xml_generator import XMLGenerator
from metrics import ConversionMetrics, MetricsCollector


@dataclass
class BatchResult:
    """Résultat d'une conversion batch"""
    pdf_file: str
    success: bool
    output_file: Optional[str] = None
    error_message: Optional[str] = None
    processing_time: float = 0.0
    metrics: Optional[ConversionMetrics] = None


@dataclass
class BatchConfig:
    """Configuration pour le traitement par lot"""
    input_paths: List[str] = field(default_factory=list)
    output_dir: str = "output"
    recursive: bool = False
    pattern: str = "*.pdf"
    workers: int = 1
    continue_on_error: bool = True
    verbose: bool = False
    progress_bar: bool = True
    taux_douanes: List[float] = field(default_factory=list)  # Taux douaniers par fichier

    def __post_init__(self):
        """Validation de la configuration"""
        if self.workers < 1:
            self.workers = 1
        if self.workers > multiprocessing.cpu_count():
            print(f"Warning: {self.workers} workers requested but only {multiprocessing.cpu_count()} CPUs available",
                  file=sys.stderr)


class BatchProcessor:
    """Gestionnaire de traitement par lot de fichiers PDF RFCV"""

    def __init__(self, config: BatchConfig):
        """
        Initialise le processeur batch

        Args:
            config: Configuration du traitement batch
        """
        self.config = config
        self.results: List[BatchResult] = []
        self.collector = MetricsCollector()

    def find_pdf_files(self) -> List[Path]:
        """
        Trouve tous les fichiers PDF selon la configuration

        Returns:
            Liste des chemins de fichiers PDF trouvés
        """
        pdf_files = []

        for input_path in self.config.input_paths:
            path = Path(input_path)

            if path.is_file():
                # Fichier direct
                if path.suffix.lower() == '.pdf':
                    pdf_files.append(path)
            elif path.is_dir():
                # Dossier - chercher les PDFs
                if self.config.recursive:
                    # Recherche récursive
                    pdf_files.extend(path.rglob(self.config.pattern))
                else:
                    # Recherche non récursive
                    pdf_files.extend(path.glob(self.config.pattern))
            else:
                print(f"Warning: '{input_path}' not found", file=sys.stderr)

        # Dédupliquer et trier
        pdf_files = sorted(set(pdf_files))

        if self.config.verbose:
            print(f"Found {len(pdf_files)} PDF file(s) to process")

        return pdf_files

    @staticmethod
    def _process_single_file(pdf_path: Path, output_dir: str, verbose: bool = False, taux_douane: Optional[float] = None) -> BatchResult:
        """
        Traite un seul fichier PDF (méthode statique pour multiprocessing)

        Args:
            pdf_path: Chemin du fichier PDF
            output_dir: Dossier de sortie
            verbose: Mode verbeux
            taux_douane: Taux de change douanier pour calcul assurance (optionnel)

        Returns:
            Résultat du traitement
        """
        result = BatchResult(
            pdf_file=str(pdf_path),
            success=False
        )

        start_time = time.time()

        try:
            # Créer le chemin de sortie
            output_file = Path(output_dir) / f"{pdf_path.stem}.xml"
            output_file.parent.mkdir(parents=True, exist_ok=True)

            # Parser le PDF
            parser = RFCVParser(str(pdf_path), taux_douane=taux_douane)
            rfcv_data = parser.parse()

            # Générer le XML
            generator = XMLGenerator(rfcv_data)
            generator.generate()
            generator.save(str(output_file), pretty_print=True)

            # Collecter les métriques
            collector = MetricsCollector()
            metrics = collector.collect_from_rfcv(str(pdf_path), rfcv_data)
            metrics.success = True
            metrics.total_time = time.time() - start_time

            # Valider le XML
            collector.validate_xml(str(output_file), metrics)

            result.success = True
            result.output_file = str(output_file)
            result.metrics = metrics
            result.processing_time = time.time() - start_time

        except Exception as e:
            result.error_message = str(e)
            result.processing_time = time.time() - start_time

            if verbose:
                import traceback
                print(f"\nError processing {pdf_path}:", file=sys.stderr)
                traceback.print_exc()

        return result

    def process_sequential(self, pdf_files: List[Path]) -> List[BatchResult]:
        """
        Traite les fichiers séquentiellement

        Args:
            pdf_files: Liste des fichiers PDF à traiter

        Returns:
            Liste des résultats de traitement
        """
        results = []

        # Créer la barre de progression si disponible
        iterator = pdf_files
        if TQDM_AVAILABLE and self.config.progress_bar:
            iterator = tqdm(pdf_files, desc="Processing PDFs", unit="file")

        for i, pdf_file in enumerate(iterator):
            # Récupérer le taux douanier pour ce fichier (si disponible)
            taux_douane = self.config.taux_douanes[i] if i < len(self.config.taux_douanes) else None

            result = self._process_single_file(
                pdf_file,
                self.config.output_dir,
                self.config.verbose,
                taux_douane=taux_douane
            )
            results.append(result)

            # Afficher le résultat si pas de barre de progression
            if not (TQDM_AVAILABLE and self.config.progress_bar):
                status = "✓" if result.success else "✗"
                print(f"  [{status}] {pdf_file.name} ({result.processing_time:.2f}s)")

        return results

    def process_parallel(self, pdf_files: List[Path]) -> List[BatchResult]:
        """
        Traite les fichiers en parallèle

        Args:
            pdf_files: Liste des fichiers PDF à traiter

        Returns:
            Liste des résultats de traitement
        """
        results = []

        with ProcessPoolExecutor(max_workers=self.config.workers) as executor:
            # Soumettre tous les jobs avec les taux douaniers
            future_to_pdf = {
                executor.submit(
                    self._process_single_file,
                    pdf_file,
                    self.config.output_dir,
                    self.config.verbose,
                    taux_douane=self.config.taux_douanes[i] if i < len(self.config.taux_douanes) else None
                ): pdf_file
                for i, pdf_file in enumerate(pdf_files)
            }

            # Créer la barre de progression si disponible
            futures = as_completed(future_to_pdf)
            if TQDM_AVAILABLE and self.config.progress_bar:
                futures = tqdm(
                    as_completed(future_to_pdf),
                    total=len(pdf_files),
                    desc=f"Processing PDFs ({self.config.workers} workers)",
                    unit="file"
                )

            # Collecter les résultats
            for future in futures:
                pdf_file = future_to_pdf[future]
                try:
                    result = future.result()
                    results.append(result)

                    # Afficher le résultat si pas de barre de progression
                    if not (TQDM_AVAILABLE and self.config.progress_bar):
                        status = "✓" if result.success else "✗"
                        print(f"  [{status}] {pdf_file.name} ({result.processing_time:.2f}s)")

                except Exception as e:
                    # En cas d'erreur lors de la récupération du résultat
                    result = BatchResult(
                        pdf_file=str(pdf_file),
                        success=False,
                        error_message=f"Future execution error: {str(e)}"
                    )
                    results.append(result)

        return results

    def process(self) -> Dict[str, Any]:
        """
        Lance le traitement batch complet

        Returns:
            Dictionnaire avec statistiques et résultats
        """
        start_time = time.time()

        # Trouver les fichiers PDF
        pdf_files = self.find_pdf_files()

        if not pdf_files:
            return {
                'success': False,
                'total_files': 0,
                'processed': 0,
                'successful': 0,
                'failed': 0,
                'results': [],
                'message': 'No PDF files found'
            }

        print(f"\n{'='*70}")
        print(f"BATCH PROCESSING: {len(pdf_files)} file(s)")
        print(f"Workers: {self.config.workers} | Output: {self.config.output_dir}")
        print(f"{'='*70}\n")

        # Traiter les fichiers (séquentiel ou parallèle)
        if self.config.workers == 1:
            self.results = self.process_sequential(pdf_files)
        else:
            self.results = self.process_parallel(pdf_files)

        # Calculer les statistiques
        total_time = time.time() - start_time
        successful = sum(1 for r in self.results if r.success)
        failed = len(self.results) - successful

        # Collecter les métriques pour les conversions réussies
        for result in self.results:
            if result.success and result.metrics:
                self.collector.add_metrics(result.metrics)

        # Afficher le résumé
        print(f"\n{'='*70}")
        print(f"BATCH COMPLETED in {total_time:.2f}s")
        print(f"{'='*70}")
        print(f"Total files: {len(pdf_files)}")
        print(f"Successful: {successful} ({successful/len(pdf_files)*100:.1f}%)")
        print(f"Failed: {failed}")
        print(f"Avg time per file: {total_time/len(pdf_files):.2f}s")

        if successful > 0:
            summary = self.collector.get_summary()
            print(f"\nQuality Metrics:")
            print(f"  Avg fill rate: {summary['avg_fill_rate']:.1f}%")
            print(f"  Avg items: {summary['avg_items_count']:.1f}")
            print(f"  Valid XMLs: {summary['xml_valid_count']}/{successful}")
            print(f"  Total warnings: {summary['total_warnings']}")

        return {
            'success': failed == 0,
            'total_files': len(pdf_files),
            'processed': len(self.results),
            'successful': successful,
            'failed': failed,
            'total_time': total_time,
            'avg_time_per_file': total_time / len(pdf_files) if pdf_files else 0,
            'results': self.results,
            'metrics_summary': self.collector.get_summary() if successful > 0 else None
        }

    def get_failed_files(self) -> List[BatchResult]:
        """Retourne la liste des fichiers qui ont échoué"""
        return [r for r in self.results if not r.success]

    def get_successful_files(self) -> List[BatchResult]:
        """Retourne la liste des fichiers traités avec succès"""
        return [r for r in self.results if r.success]
