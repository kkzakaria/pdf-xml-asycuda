"""
Batch : association des paramètres par fichier (par chemin, pas par position après tri)
et transmission du profil société.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from batch_processor import BatchConfig, BatchProcessor
from company_profile import CompanyProfile


def make_files(tmp_path, *names):
    paths = []
    for name in names:
        p = tmp_path / name
        p.write_bytes(b"%PDF-1.4")
        paths.append(str(p))
    return paths


def test_per_file_values_follow_input_order_not_sorted_order(tmp_path):
    # Ordre d'envoi : b puis a ; find_pdf_files() trie (a, b)
    b, a = make_files(tmp_path, "b.pdf", "a.pdf")
    proc = BatchProcessor(BatchConfig(
        input_paths=[b, a], taux_douanes=[600.0, 500.0],
        dossiers=["DOSSIER-B", "DOSSIER-A"], manifestes=["MAN-B", None], progress_bar=False))
    assert [p.name for p in proc.find_pdf_files()] == ["a.pdf", "b.pdf"]
    opts_a, opts_b = proc._file_options(Path(a)), proc._file_options(Path(b))
    assert (opts_a["taux_douane"], opts_a["dossier"], opts_a["manifeste"]) == (500.0, "DOSSIER-A", None)
    assert (opts_b["taux_douane"], opts_b["dossier"], opts_b["manifeste"]) == (600.0, "DOSSIER-B", "MAN-B")


def test_common_values_applied_to_all_files(tmp_path):
    files = make_files(tmp_path, "x.pdf", "y.pdf")
    profile = CompanyProfile(bureau_code="CIAB6")
    proc = BatchProcessor(BatchConfig(
        input_paths=files, taux_douane=596.302, profile=profile, insurance_mode="rfcv", takikro=True, disp=True,
        chassis_configs=[{"generate_chassis": False}], progress_bar=False))
    for f in files:
        opts = proc._file_options(Path(f))
        assert opts["taux_douane"] == 596.302
        assert opts["profile"] is profile
        assert opts["insurance_mode"] == "rfcv"
        assert opts["takikro"] is True
        assert opts["disp"] is True
        assert opts["chassis_config"] == {"generate_chassis": False}  # valeur unique répliquée
        assert opts["dossier"] is None  # jamais répliqué


def test_single_dossier_not_broadcast(tmp_path):
    files = make_files(tmp_path, "x.pdf", "y.pdf")
    proc = BatchProcessor(BatchConfig(input_paths=files, dossiers=["31287"], progress_bar=False))
    assert proc._file_options(Path(files[0]))["dossier"] == "31287"
    assert proc._file_options(Path(files[1]))["dossier"] is None
