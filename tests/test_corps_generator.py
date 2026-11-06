"""Corps SYDAM (corps_generator) : XML ASYCUDA -> corps.txt."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from corps_generator import (
    DEFAULT_PROFILE,
    corps_path_for,
    generate_corps,
    load_corps_profile,
    normalize_chassis,
    write_corps,
)

XML = """<?xml version="1.0" encoding="UTF-8"?>
<ASYCUDA>
  <Identification><Office_segment><Customs_clearance_office_code>CITKK</Customs_clearance_office_code></Office_segment>
    <Manifest_reference_number><null/></Manifest_reference_number></Identification>
  <Traders><Consignee><Consignee_code>2502282K</Consignee_code>
    <Consignee_name>SOCIETE TEST
ABIDJAN</Consignee_name></Consignee></Traders>
  <Property><Nbers><Total_number_of_packages>2</Total_number_of_packages></Nbers></Property>
  <Financial><Bank><Code>DISP</Code></Bank></Financial>
  <Transport><Border_office><Code>CITKK</Code></Border_office></Transport>
  <Item>
    <Packages><Number_of_packages>1</Number_of_packages><Marks1_of_packages>MOTO</Marks1_of_packages>
      <Marks2_of_packages>CH: LRPRPMB06TA000001</Marks2_of_packages><Kind_of_packages_code>PK</Kind_of_packages_code></Packages>
    <Tarification><Item_price>54393.0</Item_price></Tarification>
    <Previous_doc><Summary_declaration>ADM</Summary_declaration></Previous_doc>
  </Item>
  <Item>
    <Packages><Number_of_packages>1</Number_of_packages><Marks2_of_packages>LRPRPMB08TA000002</Marks2_of_packages></Packages>
    <Tarification><Item_price>54393.0</Item_price></Tarification>
  </Item>
</ASYCUDA>
"""


def lines(content):
    return [l for l in content.splitlines() if l and not l.startswith("#")]


def test_general_and_item_fields(tmp_path):
    xml = tmp_path / "dossier.xml"
    xml.write_text(XML, encoding="utf-8")
    r = generate_corps(str(xml))
    out = lines(r.content)
    assert "Fcx_Aa=CITKK" in out and "Fcx_28b=DISP" in out and "Fld_6=2" in out
    assert "Ftx_9b=SOCIETE TEST" in out                 # première ligne seulement
    assert "ITEM.1.Ftx_31b2=CH:LRPRPMB06TA000001" in out  # châssis normalisé
    assert "ITEM.2.Ftx_31b2=CH:LRPRPMB08TA000002" in out
    assert "ITEM.1.Fld_40=ADM" in out and "ITEM.1.Fcx_31f=PK" in out
    assert not any(l.startswith("Fld_Ah=") for l in out)  # <null/> : absent
    assert r.n_items == 2 and "Fld_Ah" in r.missing
    assert "# corps.txt — généré depuis dossier.xml" in r.content


def test_profile_fallback_only_when_xml_empty(tmp_path):
    xml = tmp_path / "d.xml"
    xml.write_text(XML, encoding="utf-8")
    out = lines(generate_corps(str(xml)).content)
    assert f"Fld_30={DEFAULT_PROFILE['Fld_30']}" in out    # absent du XML : profil par défaut
    assert "Fcx_29a=CITKK" in out                          # présent dans le XML : XML prioritaire
    prof = tmp_path / "p.ini"
    prof.write_text("Fld_30=QUAI   # commentaire\nFld_Ah=CIAB1 2026 7065\n", encoding="utf-8")
    out = lines(generate_corps(str(xml), load_corps_profile(str(prof))).content)
    assert "Fld_30=QUAI" in out and "Fld_Ah=CIAB1 2026 7065" in out


def test_write_corps_next_to_xml(tmp_path):
    xml = tmp_path / "rfcv_6014613.xml"
    xml.write_text(XML, encoding="utf-8")
    path, result = write_corps(xml)
    assert path == tmp_path / "corps_rfcv_6014613.txt" == corps_path_for(xml)
    assert path.read_text(encoding="utf-8") == result.content


def test_normalize_chassis():
    assert normalize_chassis("CH: ABC") == "CH:ABC" and normalize_chassis("abc") == "CH:abc"


SAMPLE_PDF = Path(__file__).resolve().parents[1] / "OT_M_2026_08746_BL_2026_07362_RFCV_v1.pdf"  # sans VIN


def test_converter_corps_option(tmp_path):
    import pytest
    if not SAMPLE_PDF.exists():
        pytest.skip("PDF d'exemple absent")
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from converter import convert_pdf_to_xml
    xml = tmp_path / "dossier.xml"
    assert convert_pdf_to_xml(str(SAMPLE_PDF), str(xml), taux_douane=576.42, corps=True)
    corps = tmp_path / "corps_dossier.txt"
    assert corps.read_text(encoding="utf-8") == generate_corps(str(xml)).content


def test_batch_corps_option(tmp_path):
    from batch_processor import BatchConfig, BatchProcessor
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    proc = BatchProcessor(BatchConfig(input_paths=[str(pdf)], corps=True, progress_bar=False))
    assert proc._file_options(pdf)["corps"] is True
