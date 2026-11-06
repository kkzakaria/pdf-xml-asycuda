"""
Service corps SYDAM : XML ASYCUDA -> corps.txt, depuis un XML converti ou envoyé.
"""
import sys
from pathlib import Path
from xml.etree.ElementTree import ParseError

from defusedxml import ElementTree as SafeET
from defusedxml.common import DefusedXmlException

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from corps_generator import CorpsResult, generate_corps

from ..core.config import settings


class CorpsError(ValueError):
    """XML refusé (illisible, entités, racine inattendue)."""


class CorpsService:
    @staticmethod
    def from_output(xml_filename: str) -> tuple[CorpsResult, str]:
        """
        Corps d'un XML de settings.output_dir (nom déjà validé, sans chemin).

        Raises:
            PermissionError: chemin résolu hors de output_dir
            FileNotFoundError: XML absent
            CorpsError: XML illisible
        """
        output_dir = Path(settings.output_dir).resolve()
        xml_path = (output_dir / xml_filename).resolve()
        try:
            xml_path.relative_to(output_dir)
        except ValueError as e:
            raise PermissionError(xml_filename) from e
        if not xml_path.is_file():
            raise FileNotFoundError(xml_filename)
        try:
            return generate_corps(str(xml_path)), xml_path.stem
        except (ParseError, DefusedXmlException) as e:
            raise CorpsError(f"XML illisible : {e}") from e

    @staticmethod
    def from_bytes(data: bytes, filename: str) -> tuple[CorpsResult, str]:
        """Corps d'un XML reçu ; lecture par defusedxml (pas d'entités ni de DTD externes)."""
        try:
            root = SafeET.fromstring(data)
        except (ParseError, DefusedXmlException) as e:
            raise CorpsError(f"XML refusé : {e}") from e
        if root.tag != "ASYCUDA":
            raise CorpsError(f"Racine <ASYCUDA> attendue, reçu <{root.tag}>")
        name = Path(filename).name
        return generate_corps(root, xml_name=name), Path(name).stem


corps_service = CorpsService()
