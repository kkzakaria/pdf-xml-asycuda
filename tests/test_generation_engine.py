"""Moteur de génération : contrôle des châssis sans écriture dans le registre."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from test_rfcv_format_2026 import MULTILINE_TEXT, parse_text

from chassis_registry import ChassisRegistry
from rfcv_parser import RFCVParser


@pytest.fixture
def registry(tmp_path):
    return ChassisRegistry(str(tmp_path / "registry.db"))


def parse_text_parser(text, registry, tmp_path, **kwargs):
    """Comme parse_text, mais rend le parseur après parse()."""
    import rfcv_parser

    class FakeExtractor:
        def __init__(self, _path):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def extract_all_text(self):
            return text

        def extract_all_tables(self):
            return []

    original = rfcv_parser.PDFExtractor
    rfcv_parser.PDFExtractor = FakeExtractor
    try:
        parser = RFCVParser(str(tmp_path / "rfcv.pdf"), registry=registry, **kwargs)
        parser.parse()
        return parser
    finally:
        rfcv_parser.PDFExtractor = original


def test_check_only_never_writes(registry, tmp_path):
    parse_text(MULTILINE_TEXT, registry, tmp_path, register_chassis=False)
    assert registry.get_all_extracted() == []


def test_check_only_reports_conflicts_instead_of_raising(registry, tmp_path):
    parse_text(MULTILINE_TEXT, registry, tmp_path)  # enregistre (défaut)
    p = parse_text_parser(MULTILINE_TEXT.replace("RCSA6099999", "RCSA6099998"), registry, tmp_path,
                          register_chassis=False)  # ne lève pas
    assert {c["first_rfcv_number"] for c in p.chassis_conflicts} == {"RCSA6099999"}
