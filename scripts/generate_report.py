#!/usr/bin/env python3
"""
Générateur de rapports pour les tests de conversion
"""
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

# Ajouter le dossier parent au path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from metrics import MetricsCollector


class ReportGenerator:
    """Générateur de rapports de test"""

    def __init__(self, collector: MetricsCollector):
        self.collector = collector
        self.summary = collector.get_summary()
        self.metrics = collector.get_all_metrics()

    def generate_markdown(self, output_file: str = "test_results.md"):
        """
        Génère un rapport au format Markdown

        Args:
            output_file: Chemin du fichier de sortie
        """
        content = []

        # En-tête
        content.append("# Rapport de Test - Convertisseur PDF RFCV → XML ASYCUDA\n")
        content.append(f"**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        content.append(f"**Tests exécutés**: {self.summary['total_conversions']}\n")

        # Résumé global
        content.append("\n## 📊 Résumé Global\n")
        content.append("| Métrique | Valeur |")
        content.append("|----------|--------|")
        content.append(f"| Conversions totales | {self.summary['total_conversions']} |")
        content.append(f"| Réussies | {self.summary['successful']} ({self.summary['success_rate']:.1f}%) |")
        content.append(f"| Échouées | {self.summary['failed']} |")
        content.append(f"| Temps moyen total | {self.summary['avg_total_time_ms']:.2f}ms |")
        content.append(f"| Temps extraction moyen | {self.summary['avg_extraction_time_ms']:.2f}ms |")
        content.append(f"| Temps génération moyen | {self.summary['avg_generation_time_ms']:.2f}ms |")
        content.append(f"| Articles extraits (moy.) | {self.summary['avg_items_count']:.1f} |")
        content.append(f"| Conteneurs extraits (moy.) | {self.summary['avg_containers_count']:.1f} |")
        content.append(f"| Taux remplissage (moy.) | {self.summary['avg_fill_rate']:.1f}% |")
        content.append(f"| XMLs valides | {self.summary['xml_valid_count']}/{self.summary['total_conversions']} |")
        content.append(f"| Warnings totaux | {self.summary['total_warnings']} |\n")

        # Détails par fichier
        content.append("\n## 📄 Détails par Fichier\n")

        for metric in self.metrics:
            status = "✅ Succès" if metric['success'] else "❌ Échec"

            content.append(f"\n### {metric['pdf_file']} - {status}\n")

            if metric['error_message']:
                content.append(f"**Erreur**: `{metric['error_message']}`\n")

            content.append("**Métriques d'extraction:**")
            content.append(f"- Pages: {metric['pages_count']}")
            content.append(f"- Taille texte: {metric['text_size']} caractères")
            content.append(f"- Tables: {metric['tables_count']}")
            content.append(f"- Temps extraction: {metric['extraction_time_ms']:.2f}ms\n")

            content.append("**Complétude des données:**")
            content.append(f"- Exportateur: {'✓' if metric['has_exporter'] else '✗'}")
            content.append(f"- Importateur: {'✓' if metric['has_consignee'] else '✗'}")
            content.append(f"- Transport: {'✓' if metric['has_transport'] else '✗'}")
            content.append(f"- Financial: {'✓' if metric['has_financial'] else '✗'}")
            content.append(f"- Valuation: {'✓' if metric['has_valuation'] else '✗'}\n")

            content.append("**Données extraites:**")
            content.append(f"- Articles: {metric['items_count']}")
            content.append(f"- Conteneurs: {metric['containers_count']}")
            content.append(f"- Valeur CIF: {metric['total_cif']}")
            content.append(f"- Valeur FOB: {metric['total_fob']}")
            content.append(f"- Poids total: {metric['total_weight']}")
            content.append(f"- Nombre de colis: {metric['total_packages']}\n")

            content.append("**Qualité XML:**")
            content.append(f"- Temps génération: {metric['generation_time_ms']:.2f}ms")
            content.append(f"- Taille XML: {metric['xml_size_kb']:.2f} KB")
            content.append(f"- XML valide: {'✓' if metric['xml_valid'] else '✗'}")
            content.append(f"- Taux remplissage: {metric['fields_filled_rate']:.1f}%\n")

            if metric['warnings']:
                content.append(f"**⚠️ Warnings ({metric['warnings_count']}):**")
                for warning in metric['warnings']:
                    content.append(f"- {warning}")
                content.append("")

        # Performance globale
        content.append("\n## ⚡ Performance\n")
        content.append("| Fichier | Temps Total (ms) | Items | Taux Remplissage |")
        content.append("|---------|------------------|-------|------------------|")

        for metric in sorted(self.metrics, key=lambda x: x['total_time_ms']):
            content.append(
                f"| {metric['pdf_file']} | "
                f"{metric['total_time_ms']:.2f} | "
                f"{metric['items_count']} | "
                f"{metric['fields_filled_rate']:.1f}% |"
            )

        # Warnings par type
        content.append("\n## ⚠️ Analyse des Warnings\n")
        warnings_by_type = {}

        for metric in self.metrics:
            for warning in metric['warnings']:
                if warning not in warnings_by_type:
                    warnings_by_type[warning] = 0
                warnings_by_type[warning] += 1

        if warnings_by_type:
            content.append("| Type de Warning | Occurrences |")
            content.append("|----------------|-------------|")
            for warning, count in sorted(warnings_by_type.items(), key=lambda x: -x[1]):
                content.append(f"| {warning} | {count} |")
        else:
            content.append("✅ Aucun warning détecté !\n")

        # Recommandations
        content.append("\n## 💡 Recommandations\n")

        if self.summary['failed'] > 0:
            content.append("- ❌ **Corriger les conversions échouées** avant mise en production")

        if self.summary['avg_fill_rate'] < 70:
            content.append("- ⚠️ **Améliorer l'extraction**: Taux de remplissage <70%")

        if "Exportateur non extrait" in warnings_by_type:
            content.append("- 🔧 **Améliorer extraction exportateur**: Ajuster les patterns regex")

        if "Importateur/Destinataire non extrait" in warnings_by_type:
            content.append("- 🔧 **Améliorer extraction importateur**: Ajuster les patterns regex")

        if "Valeur CIF manquante" in warnings_by_type:
            content.append("- 🔧 **Améliorer extraction valeurs numériques**: Vérifier patterns de parsing")

        if self.summary['xml_valid_count'] < self.summary['total_conversions']:
            content.append("- ⚠️ **Valider structure XML**: Certains XMLs ne sont pas valides")

        if len(warnings_by_type) == 0 and self.summary['failed'] == 0:
            content.append("✅ **Système optimal** - Aucune amélioration critique nécessaire\n")

        # Écrire le fichier
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(content))

        print(f"\n📝 Rapport Markdown généré: {output_file}")

    def generate_json(self, output_file: str = "test_results.json"):
        """
        Génère un rapport au format JSON

        Args:
            output_file: Chemin du fichier de sortie
        """
        report = {
            'generated_at': datetime.now().isoformat(),
            'summary': self.summary,
            'metrics': self.metrics
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        print(f"📊 Rapport JSON généré: {output_file}")

    def generate_all(self, md_file: str = "test_results.md", json_file: str = "test_results.json"):
        """
        Génère tous les rapports

        Args:
            md_file: Fichier Markdown
            json_file: Fichier JSON
        """
        self.generate_markdown(md_file)
        self.generate_json(json_file)


def main():
    """Point d'entrée principal"""
    print("⚠️ Ce script doit être utilisé via tests/test_converter.py")
    print("Usage: python tests/test_converter.py -d tests/ -v")
    sys.exit(1)


if __name__ == '__main__':
    main()
