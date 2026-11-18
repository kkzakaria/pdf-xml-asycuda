"""CLI : la conversion contrôle seulement les doublons ; l'enregistrement est explicite."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

import converter
import rfcv_parser
from chassis_registry import ChassisRegistry
from tests.test_rfcv_format_2026 import MULTILINE_TEXT


@pytest.fixture
def env(tmp_path, monkeypatch):
    registry = ChassisRegistry(tmp_path / "r.db")
    monkeypatch.setattr(rfcv_parser, "get_registry", lambda: registry)

    class FakeExtractor:
        def __init__(self, _path):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def extract_all_text(self):
            return MULTILINE_TEXT

        def extract_all_tables(self):
            return []

    monkeypatch.setattr(rfcv_parser, "PDFExtractor", FakeExtractor)
    pdf = tmp_path / "rfcv.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    return registry, pdf, tmp_path


def _convert(pdf, tmp_path, name, **kw):
    return converter.convert_pdf_to_xml(str(pdf), str(tmp_path / name), **kw)


def _count(registry):
    import sqlite3
    with sqlite3.connect(registry.db_path) as c:
        return c.execute("SELECT COUNT(*) FROM extracted_chassis").fetchone()[0]


def test_cli_default_does_not_register(env, capsys):
    registry, pdf, tmp_path = env
    assert _convert(pdf, tmp_path, "a.xml") is True
    assert _count(registry) == 0
    # Une seconde conversion réussit aussi (rien n'a été enregistré)
    assert _convert(pdf, tmp_path, "b.xml") is True


def test_cli_flag_registers(env):
    registry, pdf, tmp_path = env
    assert _convert(pdf, tmp_path, "a.xml", register_chassis=True) is True
    assert _count(registry) == 3


def test_cli_flag_refuses_duplicate(env, capsys):
    registry, pdf, tmp_path = env
    assert _convert(pdf, tmp_path, "a.xml", register_chassis=True) is True
    assert _convert(pdf, tmp_path, "b.xml", register_chassis=True) is False
    assert "déjà traité" in capsys.readouterr().err


def test_cli_default_warns_on_existing_duplicate(env, capsys):
    registry, pdf, tmp_path = env
    _convert(pdf, tmp_path, "a.xml", register_chassis=True)
    capsys.readouterr()
    assert _convert(pdf, tmp_path, "b.xml") is True
    err = capsys.readouterr().err
    assert "Attention" in err and "3 châssis" in err


def test_batch_check_only_reports_conflicts(env):
    from batch_processor import BatchProcessor
    registry, pdf, tmp_path = env
    assert _convert(pdf, tmp_path, "a.xml", register_chassis=True) is True
    res = BatchProcessor._process_single_file(pdf, str(tmp_path / "out"))
    assert res.success and len(res.chassis_conflicts) == 3
    assert "3 châssis déjà traité(s)" in res.conflict_warning()
    import pickle
    assert pickle.loads(pickle.dumps(res)).chassis_conflicts == res.chassis_conflicts


def test_batch_default_does_not_register_and_flag_refuses(env):
    from batch_processor import BatchProcessor
    registry, pdf, tmp_path = env
    r1 = BatchProcessor._process_single_file(pdf, str(tmp_path / "out"))
    assert r1.success and not r1.chassis_conflicts and _count(registry) == 0
    r2 = BatchProcessor._process_single_file(pdf, str(tmp_path / "out"), register_chassis=True)
    assert r2.success and _count(registry) == 3
    r3 = BatchProcessor._process_single_file(pdf, str(tmp_path / "out"), register_chassis=True)
    assert not r3.success and "châssis" in r3.error_message.lower()


def test_batch_report_csv_includes_chassis_warning(env):
    from batch_processor import BatchProcessor
    from batch_report import BatchReportGenerator
    registry, pdf, tmp_path = env
    _convert(pdf, tmp_path, "a.xml", register_chassis=True)
    res = BatchProcessor._process_single_file(pdf, str(tmp_path / "out"))
    gen = BatchReportGenerator({"results": [res], "total_files": 1, "successful": 1, "failed": 0,
                                "total_time": 1.0, "success": True})
    gen.generate_csv(str(tmp_path / "r.csv"))
    assert "3 châssis déjà traité(s)" in (tmp_path / "r.csv").read_text(encoding="utf-8")
