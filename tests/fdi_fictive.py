"""
FDI fictive pour les tests : PDF minimal (une page A4, Helvetica 8) dont chaque texte est posé
à une position donnée, comme l'impression DGCE (valeur 11,5 points sous son étiquette).
Aucune vraie FDI dans le dépôt.
"""
from pathlib import Path

HAUTEUR = 842.0


def _echapper(texte: str) -> bytes:
    brut = texte.encode("cp1252")
    return brut.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def ecrire_pdf(chemin: Path, textes: list[tuple[float, float, str]]) -> Path:
    """textes = [(x, top, texte)] ; top mesuré depuis le haut de la page, comme pdfplumber."""
    flux = b"BT /F1 8 Tf\n"
    for x, top, texte in textes:
        y = HAUTEUR - top - 6     # ligne de base : sous le haut du texte (corps 8)
        flux += b"1 0 0 1 %.1f %.1f Tm (" % (x, y) + _echapper(texte) + b") Tj\n"
    flux += b"ET\n"
    objets = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(flux) + flux + b"endstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]
    sortie = b"%PDF-1.4\n"
    positions = []
    for i, obj in enumerate(objets, 1):
        positions.append(len(sortie))
        sortie += b"%d 0 obj\n" % i + obj + b"\nendobj\n"
    xref = len(sortie)
    sortie += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objets) + 1)
    sortie += b"".join(b"%010d 00000 n \n" % p for p in positions)
    sortie += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objets) + 1, xref)
    Path(chemin).write_bytes(sortie)
    return Path(chemin)


def fdi_fictive(chemin: Path, numero: str = "260100001", date_validation: str = "02/11/2026",
                date_soumission: str = "28/10/2026") -> Path:
    """FDI fictive à la mise en page DGCE (positions relevées sur une FDI réelle)."""
    return ecrire_pdf(chemin, [
        (500.0, 28.9, "FDI"),
        (306.0, 162.0, "4. N° FDI"), (446.0, 162.0, "5. Date Validation"),
        (306.0, 173.5, numero), (446.0, 173.5, date_validation),
        (306.0, 300.0, "Date Facture :"), (356.0, 300.5, "13/10/2026"),
        (445.0, 404.0, "21. Date Domiciliation"), (445.0, 414.5, "01/11/2026"),
        (469.0, 811.0, "Date Soumission"), (532.0, 811.0, date_soumission),
    ])
