"""
Module d'extraction de données depuis les fichiers PDF RFCV
Utilise pdfplumber pour extraire le texte et les tables
"""
import pdfplumber
import re
from typing import Dict, List, Optional, Any, Tuple
import pandas as pd


class PDFExtractor:
    """Extracteur de données depuis PDF RFCV"""

    def __init__(self, pdf_path: str):
        """
        Initialise l'extracteur avec le chemin du PDF

        Args:
            pdf_path: Chemin vers le fichier PDF RFCV
        """
        self.pdf_path = pdf_path
        self.pdf = None
        self.text_content = ""
        self.tables = []

    def __enter__(self):
        """Support pour context manager"""
        self.pdf = pdfplumber.open(self.pdf_path)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Fermeture automatique du PDF"""
        if self.pdf:
            self.pdf.close()

    def extract_all_text(self) -> str:
        """
        Extrait tout le texte du PDF

        Returns:
            Texte complet du document
        """
        if not self.pdf:
            raise RuntimeError("PDF not opened. Use 'with' statement.")

        text_parts = []
        for page in self.pdf.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)

        self.text_content = "\n".join(text_parts)
        return self.text_content

    def extract_all_tables(self) -> List[pd.DataFrame]:
        """
        Extrait toutes les tables du PDF

        Returns:
            Liste de DataFrames contenant les tables
        """
        if not self.pdf:
            raise RuntimeError("PDF not opened. Use 'with' statement.")

        self.tables = []
        for page in self.pdf.pages:
            page_tables = page.extract_tables()
            for table in page_tables:
                if table:
                    # Convertir en DataFrame avec première ligne comme header
                    df = pd.DataFrame(table[1:], columns=table[0])
                    self.tables.append(df)

        return self.tables

    def extract_field(self, pattern: str, text: Optional[str] = None) -> Optional[str]:
        """
        Extrait un champ spécifique en utilisant une regex

        Args:
            pattern: Pattern regex à rechercher
            text: Texte à analyser (utilise self.text_content si None)

        Returns:
            Valeur extraite ou None
        """
        search_text = text if text is not None else self.text_content
        match = re.search(pattern, search_text, re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(1).strip() if match.lastindex else match.group(0).strip()
        return None

    def extract_fields(self, patterns: Dict[str, str], text: Optional[str] = None) -> Dict[str, Optional[str]]:
        """
        Extrait plusieurs champs en utilisant un dictionnaire de patterns

        Args:
            patterns: Dictionnaire {nom_champ: pattern_regex}
            text: Texte à analyser (utilise self.text_content si None)

        Returns:
            Dictionnaire {nom_champ: valeur_extraite}
        """
        results = {}
        search_text = text if text is not None else self.text_content

        for field_name, pattern in patterns.items():
            results[field_name] = self.extract_field(pattern, search_text)

        return results

    def extract_section(self, start_marker: str, end_marker: Optional[str] = None) -> str:
        """
        Extrait une section du texte entre deux marqueurs

        Args:
            start_marker: Marqueur de début
            end_marker: Marqueur de fin (optionnel)

        Returns:
            Texte de la section
        """
        if not self.text_content:
            self.extract_all_text()

        start_pos = self.text_content.find(start_marker)
        if start_pos == -1:
            return ""

        start_pos += len(start_marker)

        if end_marker:
            end_pos = self.text_content.find(end_marker, start_pos)
            if end_pos != -1:
                return self.text_content[start_pos:end_pos].strip()

        return self.text_content[start_pos:].strip()

    def extract_table_by_header(self, header_keywords: List[str]) -> Optional[pd.DataFrame]:
        """
        Trouve une table contenant certains mots-clés dans l'en-tête

        Args:
            header_keywords: Mots-clés à rechercher dans les colonnes

        Returns:
            DataFrame de la table trouvée ou None
        """
        if not self.tables:
            self.extract_all_tables()

        for table in self.tables:
            columns_str = " ".join([str(col).lower() for col in table.columns])
            if all(keyword.lower() in columns_str for keyword in header_keywords):
                return table

        return None

    def extract_multiline_field(self, label: str, lines_count: int = 3) -> str:
        """
        Extrait un champ qui peut s'étendre sur plusieurs lignes

        Args:
            label: Étiquette du champ
            lines_count: Nombre de lignes à capturer

        Returns:
            Valeur multi-lignes
        """
        if not self.text_content:
            self.extract_all_text()

        # Cherche le label et capture les N lignes suivantes
        pattern = rf"{re.escape(label)}[:\s]*\n?((?:.*\n?){{1,{lines_count}}})"
        match = re.search(pattern, self.text_content, re.IGNORECASE)

        if match:
            lines = match.group(1).strip()
            # Nettoie les lignes vides multiples
            lines = re.sub(r'\n\s*\n', '\n', lines)
            return lines

        return ""

    def extract_coordinates_text(self, x0: float, y0: float, x1: float, y1: float, page_num: int = 0) -> str:
        """
        Extrait le texte d'une zone spécifique par coordonnées

        Args:
            x0, y0: Coordonnées coin supérieur gauche
            x1, y1: Coordonnées coin inférieur droit
            page_num: Numéro de page (0-indexed)

        Returns:
            Texte de la zone
        """
        if not self.pdf:
            raise RuntimeError("PDF not opened. Use 'with' statement.")

        if page_num >= len(self.pdf.pages):
            return ""

        page = self.pdf.pages[page_num]
        bbox = (x0, y0, x1, y1)
        cropped = page.crop(bbox)
        text = cropped.extract_text()

        return text.strip() if text else ""

    def get_page_count(self) -> int:
        """Retourne le nombre de pages du PDF"""
        if not self.pdf:
            raise RuntimeError("PDF not opened. Use 'with' statement.")
        return len(self.pdf.pages)

    def debug_extract(self, output_file: str = "debug_extraction.txt"):
        """
        Extrait et sauvegarde tout le contenu pour debug

        Args:
            output_file: Fichier de sortie pour le debug
        """
        text = self.extract_all_text()
        tables = self.extract_all_tables()

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("="*80 + "\n")
            f.write("TEXTE COMPLET\n")
            f.write("="*80 + "\n\n")
            f.write(text)
            f.write("\n\n" + "="*80 + "\n")
            f.write("TABLES EXTRAITES\n")
            f.write("="*80 + "\n\n")

            for i, table in enumerate(tables):
                f.write(f"\n--- Table {i+1} ---\n")
                f.write(table.to_string())
                f.write("\n")

        print(f"Debug extraction saved to: {output_file}")
        return text, tables


def extract_pdf_data(pdf_path: str) -> Tuple[str, List[pd.DataFrame]]:
    """
    Fonction utilitaire pour extraire rapidement texte et tables

    Args:
        pdf_path: Chemin du fichier PDF

    Returns:
        Tuple (texte, liste_tables)
    """
    with PDFExtractor(pdf_path) as extractor:
        text = extractor.extract_all_text()
        tables = extractor.extract_all_tables()
        return text, tables
