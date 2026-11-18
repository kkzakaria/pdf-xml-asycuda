"""Désignation courte : proposition et application (case 31 et description marchandise)."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from designation import apply_designation, suggest_designation
from models import Item, Package, RFCVData


@pytest.mark.parametrize("raw,expected", [
    ("TRICYLE-APSONIC-", "TRICYCLE"), ("TRICYCLE - APSONIC -", "TRICYCLE"), ("TRICYCLE-APSONIC -", "TRICYCLE"),
    ("MOTO-APSONIC-", "MOTO"), ("MOTORCYCLE", "MOTO"), ("MOTO", None), ("TRICYCLE", None), ("PNEUS", None)])
def test_suggest(raw, expected):
    assert suggest_designation(raw) == expected


def test_apply_sets_marks_and_description():
    d = RFCVData(items=[Item(packages=Package(marks1="TRICYLE-APSONIC-"), goods_description="TRICYLE-APSONIC-")])
    assert apply_designation(d, "TRICYCLE") == 1
    assert (d.items[0].packages.marks1, d.items[0].goods_description) == ("TRICYCLE", "TRICYCLE")
