"""
Service de gestion des jobs
Tracking simple en mémoire (peut être étendu vers DB)
"""
from typing import Dict, Optional, List
from datetime import datetime
from ..models.api_models import JobStatus


class JobService:
    """Service de tracking des jobs"""

    def __init__(self):
        # Storage en mémoire des jobs
        self.jobs: Dict[str, Dict] = {}
        self.batches: Dict[str, Dict] = {}

    def create_job(
        self,
        job_id: str,
        filename: str,
        pdf_path: str,
        output_path: Optional[str] = None
    ) -> Dict:
        """
        Crée un nouveau job de conversion

        Args:
            job_id: ID du job
            filename: Nom du fichier
            pdf_path: Chemin du PDF
            output_path: Chemin de sortie XML

        Returns:
            Job créé
        """
        job = {
            'job_id': job_id,
            'filename': filename,
            'pdf_path': pdf_path,
            'output_path': output_path,
            'status': JobStatus.PENDING,
            'created_at': datetime.now(),
            'completed_at': None,
            'progress': 0,
            'message': 'Job créé',
            'error': None,
            'result': None
        }

        self.jobs[job_id] = job
        return job

    def update_job(
        self,
        job_id: str,
        status: Optional[JobStatus] = None,
        progress: Optional[int] = None,
        message: Optional[str] = None,
        error: Optional[str] = None,
        result: Optional[Dict] = None
    ) -> Optional[Dict]:
        """
        Met à jour un job

        Args:
            job_id: ID du job
            status: Nouveau status
            progress: Progression (0-100)
            message: Message
            error: Message d'erreur
            result: Résultat de la conversion

        Returns:
            Job mis à jour ou None
        """
        if job_id not in self.jobs:
            return None

        job = self.jobs[job_id]

        if status:
            job['status'] = status
            if status in [JobStatus.COMPLETED, JobStatus.FAILED]:
                job['completed_at'] = datetime.now()

        if progress is not None:
            job['progress'] = progress

        if message:
            job['message'] = message

        if error:
            job['error'] = error

        if result:
            job['result'] = result

        return job

    def get_job(self, job_id: str) -> Optional[Dict]:
        """
        Récupère un job

        Args:
            job_id: ID du job

        Returns:
            Job ou None
        """
        return self.jobs.get(job_id)

    def create_batch(
        self,
        batch_id: str,
        total_files: int,
        pdf_paths: List[str]
    ) -> Dict:
        """
        Crée un batch job

        Args:
            batch_id: ID du batch
            total_files: Nombre total de fichiers
            pdf_paths: Liste des chemins PDF

        Returns:
            Batch créé
        """
        batch = {
            'batch_id': batch_id,
            'total_files': total_files,
            'pdf_paths': pdf_paths,
            'processed': 0,
            'successful': 0,
            'failed': 0,
            'status': JobStatus.PENDING,
            'created_at': datetime.now(),
            'completed_at': None,
            'message': 'Batch créé',
            'results': []
        }

        self.batches[batch_id] = batch
        return batch

    def update_batch(
        self,
        batch_id: str,
        status: Optional[JobStatus] = None,
        processed: Optional[int] = None,
        successful: Optional[int] = None,
        failed: Optional[int] = None,
        message: Optional[str] = None,
        results: Optional[List] = None
    ) -> Optional[Dict]:
        """
        Met à jour un batch

        Args:
            batch_id: ID du batch
            status: Nouveau status
            processed: Nombre traités
            successful: Nombre réussis
            failed: Nombre échoués
            message: Message
            results: Résultats

        Returns:
            Batch mis à jour ou None
        """
        if batch_id not in self.batches:
            return None

        batch = self.batches[batch_id]

        if status:
            batch['status'] = status
            if status in [JobStatus.COMPLETED, JobStatus.FAILED]:
                batch['completed_at'] = datetime.now()

        if processed is not None:
            batch['processed'] = processed

        if successful is not None:
            batch['successful'] = successful

        if failed is not None:
            batch['failed'] = failed

        if message:
            batch['message'] = message

        if results:
            batch['results'] = results

        return batch

    def get_batch(self, batch_id: str) -> Optional[Dict]:
        """
        Récupère un batch

        Args:
            batch_id: ID du batch

        Returns:
            Batch ou None
        """
        return self.batches.get(batch_id)

    def get_all_jobs(self) -> List[Dict]:
        """Retourne tous les jobs"""
        return list(self.jobs.values())

    def get_all_batches(self) -> List[Dict]:
        """Retourne tous les batches"""
        return list(self.batches.values())

    def cleanup_old_jobs(self, max_age_hours: int = 24):
        """
        Nettoie les vieux jobs

        Args:
            max_age_hours: Âge maximum en heures
        """
        now = datetime.now()
        cutoff = now.timestamp() - (max_age_hours * 3600)

        # Nettoyer jobs
        to_delete = [
            job_id for job_id, job in self.jobs.items()
            if job['created_at'].timestamp() < cutoff
        ]
        for job_id in to_delete:
            del self.jobs[job_id]

        # Nettoyer batches
        to_delete = [
            batch_id for batch_id, batch in self.batches.items()
            if batch['created_at'].timestamp() < cutoff
        ]
        for batch_id in to_delete:
            del self.batches[batch_id]


# Instance globale (singleton)
job_service = JobService()
