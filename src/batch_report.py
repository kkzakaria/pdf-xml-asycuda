"""
Générateur de rapports pour le traitement par lot
Supporte les formats JSON, CSV et Markdown
"""
import json
import csv
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List
from dataclasses import asdict


class BatchReportGenerator:
    """Générateur de rapports pour traitement batch"""

    def __init__(self, batch_results: Dict[str, Any]):
        """
        Initialise le générateur de rapports

        Args:
            batch_results: Résultats du traitement batch
        """
        self.batch_results = batch_results
        self.timestamp = datetime.now()

    def generate_json(self, output_file: str) -> None:
        """
        Génère un rapport au format JSON

        Args:
            output_file: Chemin du fichier de sortie
        """
        report = {
            'generated_at': self.timestamp.isoformat(),
            'summary': {
                'total_files': self.batch_results['total_files'],
                'processed': self.batch_results['processed'],
                'successful': self.batch_results['successful'],
                'failed': self.batch_results['failed'],
                'success_rate': round(
                    self.batch_results['successful'] / self.batch_results['total_files'] * 100, 2
                ) if self.batch_results['total_files'] > 0 else 0,
                'total_time': round(self.batch_results['total_time'], 2),
                'avg_time_per_file': round(self.batch_results['avg_time_per_file'], 2)
            },
            'quality_metrics': self.batch_results.get('metrics_summary'),
            'files': []
        }

        # Ajouter les détails de chaque fichier
        for result in self.batch_results['results']:
            file_info = {
                'file': result.pdf_file,
                'success': result.success,
                'output_file': result.output_file,
                'processing_time': round(result.processing_time, 3),
                'error': result.error_message if not result.success else None
            }

            # Ajouter les métriques si disponibles
            if result.metrics:
                file_info['metrics'] = {
                    'items_count': result.metrics.items_count,
                    'containers_count': result.metrics.containers_count,
                    'fill_rate': round(result.metrics.fields_filled_rate, 2),
                    'warnings_count': len(result.metrics.warnings),
                    'warnings': result.metrics.warnings,
                    'xml_valid': result.metrics.xml_valid,
                    'has_exporter': result.metrics.has_exporter,
                    'has_consignee': result.metrics.has_consignee
                }

            report['files'].append(file_info)

        # Écrire le fichier JSON
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        print(f"📊 JSON report generated: {output_file}")

    def generate_csv(self, output_file: str) -> None:
        """
        Génère un rapport au format CSV

        Args:
            output_file: Chemin du fichier de sortie
        """
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            # Définir les colonnes
            fieldnames = [
                'file', 'success', 'output_file', 'processing_time',
                'items_count', 'containers_count', 'fill_rate',
                'xml_valid', 'warnings_count', 'error'
            ]

            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            # Écrire les données
            for result in self.batch_results['results']:
                row = {
                    'file': Path(result.pdf_file).name,
                    'success': 'Yes' if result.success else 'No',
                    'output_file': Path(result.output_file).name if result.output_file else '',
                    'processing_time': round(result.processing_time, 3),
                    'items_count': result.metrics.items_count if result.metrics else '',
                    'containers_count': result.metrics.containers_count if result.metrics else '',
                    'fill_rate': round(result.metrics.fields_filled_rate, 1) if result.metrics else '',
                    'xml_valid': 'Yes' if result.metrics and result.metrics.xml_valid else 'No',
                    'warnings_count': len(result.metrics.warnings) if result.metrics else '',
                    'error': result.error_message if not result.success else ''
                }
                writer.writerow(row)

        print(f"📊 CSV report generated: {output_file}")

    def generate_markdown(self, output_file: str) -> None:
        """
        Génère un rapport au format Markdown

        Args:
            output_file: Chemin du fichier de sortie
        """
        lines = []

        # En-tête
        lines.append("# Rapport Batch - Conversion PDF RFCV → XML ASYCUDA\n")
        lines.append(f"**Date**: {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n")
        lines.append(f"**Fichiers traités**: {self.batch_results['total_files']}\n")

        # Résumé global
        lines.append("\n## 📊 Résumé Global\n")
        lines.append("| Métrique | Valeur |")
        lines.append("|----------|--------|")
        lines.append(f"| Fichiers totaux | {self.batch_results['total_files']} |")
        lines.append(f"| Traités | {self.batch_results['processed']} |")

        success_rate = (self.batch_results['successful'] / self.batch_results['total_files'] * 100
                       ) if self.batch_results['total_files'] > 0 else 0
        lines.append(f"| Réussis | {self.batch_results['successful']} ({success_rate:.1f}%) |")
        lines.append(f"| Échoués | {self.batch_results['failed']} |")
        lines.append(f"| Temps total | {self.batch_results['total_time']:.2f}s |")
        lines.append(f"| Temps moyen/fichier | {self.batch_results['avg_time_per_file']:.2f}s |")

        # Métriques de qualité
        if self.batch_results.get('metrics_summary'):
            summary = self.batch_results['metrics_summary']
            lines.append("\n## 📈 Métriques de Qualité\n")
            lines.append("| Métrique | Valeur |")
            lines.append("|----------|--------|")
            lines.append(f"| Taux de remplissage moyen | {summary['avg_fill_rate']:.1f}% |")
            lines.append(f"| Articles moyens par fichier | {summary['avg_items_count']:.1f} |")
            lines.append(f"| Conteneurs moyens par fichier | {summary['avg_containers_count']:.1f} |")
            lines.append(f"| XMLs valides | {summary['xml_valid_count']}/{self.batch_results['successful']} |")
            lines.append(f"| Warnings totaux | {summary['total_warnings']} |")

        # Tableau détaillé des fichiers
        lines.append("\n## 📄 Détails par Fichier\n")
        lines.append("| Fichier | Statut | Temps | Articles | Remplissage | Warnings |")
        lines.append("|---------|--------|-------|----------|-------------|----------|")

        for result in self.batch_results['results']:
            filename = Path(result.pdf_file).name
            status = "✅" if result.success else "❌"
            time_str = f"{result.processing_time:.2f}s"

            if result.metrics:
                items = result.metrics.items_count
                fill_rate = f"{result.metrics.fields_filled_rate:.1f}%"
                warnings = len(result.metrics.warnings)
            else:
                items = "-"
                fill_rate = "-"
                warnings = "-"

            lines.append(f"| {filename} | {status} | {time_str} | {items} | {fill_rate} | {warnings} |")

        # Fichiers échoués (si présents)
        failed_results = [r for r in self.batch_results['results'] if not r.success]
        if failed_results:
            lines.append("\n## ❌ Fichiers Échoués\n")
            for result in failed_results:
                lines.append(f"### {Path(result.pdf_file).name}\n")
                lines.append(f"**Erreur**: `{result.error_message}`\n")

        # Performance
        lines.append("\n## ⚡ Performance\n")
        sorted_results = sorted(self.batch_results['results'], key=lambda x: x.processing_time)

        lines.append("**Top 5 plus rapides:**\n")
        for result in sorted_results[:5]:
            filename = Path(result.pdf_file).name
            lines.append(f"- {filename}: {result.processing_time:.2f}s")

        if len(sorted_results) > 5:
            lines.append("\n**Top 5 plus lents:**\n")
            for result in sorted_results[-5:]:
                filename = Path(result.pdf_file).name
                lines.append(f"- {filename}: {result.processing_time:.2f}s")

        # Écrire le fichier
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

        print(f"📊 Markdown report generated: {output_file}")

    def generate_all(self, base_filename: str = "batch_report") -> None:
        """
        Génère tous les formats de rapport

        Args:
            base_filename: Nom de base pour les fichiers (sans extension)
        """
        timestamp_str = self.timestamp.strftime('%Y%m%d_%H%M%S')
        base = f"{base_filename}_{timestamp_str}"

        self.generate_json(f"{base}.json")
        self.generate_csv(f"{base}.csv")
        self.generate_markdown(f"{base}.md")

        print(f"\n✓ All batch reports generated with prefix: {base}")
