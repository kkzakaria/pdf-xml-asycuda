"""Annulation d'un RFCV dans le registre des châssis (RFCV annulé, éclaté en d'autres RFCV)."""
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from test_rfcv_format_2026 import MULTILINE_TEXT, parse_text

from chassis_registry import ChassisRegistry, DuplicateChassisError, normalize_rfcv


@pytest.fixture
def registry(tmp_path):
    return ChassisRegistry(str(tmp_path / "registry.db"))


def fill(reg, rfcv, vins):
    for v in vins:
        reg.register_extracted(v, f"rfcv_{rfcv}.pdf", rfcv)


def test_normalize_rfcv():
    assert normalize_rfcv("RCSA6014576") == normalize_rfcv(" rcsa 6014576 ") == normalize_rfcv("6014576") == "6014576"
    assert normalize_rfcv("RCS26159491") == "26159491"
    assert normalize_rfcv("RCSA6099999-P1") == "6099999-P1"
    assert normalize_rfcv(None) == ""


def test_cancel_moves_chassis_to_history(registry):
    fill(registry, "RCSA6014576", ["VIN00000000000001", "VIN00000000000002"])
    fill(registry, "RCSA6014577", ["VIN00000000000003"])
    cancelled = registry.cancel_rfcv("6014576", "Annulé par la société d'inspection")
    assert cancelled == ["VIN00000000000001", "VIN00000000000002"]
    assert registry.check_extracted("VIN00000000000001") is None
    assert registry.check_extracted("VIN00000000000003") is not None      # autre RFCV intact
    hist = registry.get_cancelled(rfcv_number="RCSA6014576")
    assert {h["chassis_number"] for h in hist} == set(cancelled)
    assert all(h["reason"] == "Annulé par la société d'inspection" and h["restored_at"] is None for h in hist)
    assert hist[0]["filename"] == "rfcv_RCSA6014576.pdf"


def test_cancel_subset_and_validation(registry):
    fill(registry, "RCSA6014576", ["VIN00000000000001", "VIN00000000000002"])
    assert registry.cancel_rfcv("RCSA6014576", "partiel", ["vin00000000000002"]) == ["VIN00000000000002"]
    assert registry.check_extracted("VIN00000000000001") is not None
    assert registry.cancel_rfcv("RCSA9999999", "inconnu") == []
    with pytest.raises(ValueError):
        registry.cancel_rfcv("RCSA6014576", "  ")


def test_restore_and_conflicts(registry):
    fill(registry, "RCSA6014576", ["VIN00000000000001", "VIN00000000000002"])
    registry.cancel_rfcv("RCSA6014576", "erreur de manipulation")
    fill(registry, "RCSA6014621", ["VIN00000000000002"])                   # repris entre-temps
    r = registry.restore_rfcv("6014576")
    assert r == {"restored": ["VIN00000000000001"], "conflicts": ["VIN00000000000002"]}
    assert registry.check_extracted("VIN00000000000001")["rfcv_number"] == "RCSA6014576"
    assert registry.check_extracted("VIN00000000000002")["rfcv_number"] == "RCSA6014621"
    assert registry.restore_rfcv("6014576") == {"restored": [], "conflicts": ["VIN00000000000002"]}


def test_split_rfcv_scenario(registry, tmp_path):
    """RFCV d'origine traité, puis annulé et éclaté : le nouveau RFCV reprend ses châssis."""
    original = parse_text(MULTILINE_TEXT, registry, tmp_path)
    vins = [i.packages.marks2 for i in original.items if i.packages and i.packages.marks2]
    assert vins and registry.check_extracted(vins[0].replace("CH:", "").strip())["rfcv_number"] == "RCSA6099999"

    split = MULTILINE_TEXT.replace("RCSA6099999", "RCSA6099998")
    with pytest.raises(DuplicateChassisError) as e:
        parse_text(split, registry, tmp_path)
    assert {d["first_rfcv_number"] for d in e.value.duplicates} == {"RCSA6099999"}

    assert len(registry.cancel_rfcv("RCSA6099999", "éclaté en RCSA6099998")) == len(e.value.duplicates)
    data = parse_text(split, registry, tmp_path)
    assert len(data.items) == len(original.items)
    for d in e.value.duplicates:
        assert registry.check_extracted(d["chassis_number"])["rfcv_number"] == "RCSA6099998"


def run_cli(db, *args):
    return subprocess.run([sys.executable, str(ROOT / "registre.py"), "--db", str(db), *args],
                          capture_output=True, text=True, cwd=ROOT, check=False)


def test_cli(tmp_path):
    db = tmp_path / "registry.db"
    fill(ChassisRegistry(str(db)), "RCSA6014576", ["VIN00000000000001", "VIN00000000000002"])
    r = run_cli(db, "annuler", "6014576")
    assert r.returncode != 0                                                # --motif obligatoire
    r = run_cli(db, "annuler", "6014576", "--motif", "Éclaté en 6014621")
    assert r.returncode == 0 and "2 châssis" in r.stdout, r.stderr
    r = run_cli(db, "annulations", "--details")
    assert "RCSA6014576" in r.stdout and "Éclaté en 6014621" in r.stdout and "VIN00000000000001" in r.stdout
    r = run_cli(db, "chercher", "vin00000000000001")
    assert "absent du registre actif" in r.stdout and "annulé le" in r.stdout
    assert run_cli(db, "annuler", "6014576", "--motif", "x").returncode == 1   # plus rien à annuler
    r = run_cli(db, "restaurer", "RCSA6014576")
    assert r.returncode == 0 and "2 châssis" in r.stdout
    assert "RCSA6014576" in run_cli(db, "chercher", "VIN00000000000001").stdout
