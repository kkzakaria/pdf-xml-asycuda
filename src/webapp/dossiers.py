"""
Cycle d'un dossier (spécification §5.2) : brouillon, générations, « Déclaré dans SYDAM »,
retour en brouillon par un administrateur.

- Générer n'écrit jamais dans le registre des châssis ; les châssis déjà déclarés ou présents
  dans un autre brouillon apparaissent en alertes dans le résumé.
- Déclarer refait le contrôle des châssis contre le registre (il a pu changer depuis la
  génération) puis enregistre les VIN de la dernière génération.
- Fichiers sous data_dir/dossiers/<id>/ (PDF d'origine, puis gen-<n>/ par génération),
  jamais écrasés. Chaque changement d'état est inscrit dans la table events.
"""
from __future__ import annotations

import json
import logging
import re
import shutil
import sqlite3
import sys
import threading
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pdf_extractor  # noqa: E402
import rfcv_format_2026 as fmt  # noqa: E402
from chassis_registry import ChassisRegistry, normalize_rfcv  # noqa: E402
from company_profile import load_profile  # noqa: E402
from designation import suggest_designation  # noqa: E402
from generation import GenerationSettings, generate as generate_drafts  # noqa: E402
from generation_summary import Summary  # noqa: E402

from . import db  # noqa: E402
from .auth import User  # noqa: E402
from .config import WebappSettings  # noqa: E402

logger = logging.getLogger(__name__)

RFCV_NUMBER = re.compile(r"RCS[A-Z]?\d+(?:-P\d+)?")
FIGES = ("declare", "annule")

# Déclarations sérialisées : contrôle du registre puis écriture sans entrelacement.
_declare_lock = threading.Lock()


class DossierIntrouvable(LookupError):
    """Aucun dossier avec cet identifiant."""


class DossierFige(Exception):
    """Dossier déclaré ou annulé : ni régénéré ni redéclaré."""


class DeclarationRefusee(Exception):
    """Passage « Déclaré dans SYDAM » refusé. conflicts = [{chassis_number, rfcv_number, filename}]."""

    def __init__(self, message: str, conflicts: list[dict] | None = None):
        super().__init__(message)
        self.message = message
        self.conflicts = conflicts or []


# ------------------------------------------------------------------ utilitaires
def _safe_filename(filename: str) -> str:
    """Nom de fichier sans chemin ni caractère spécial, extension .pdf."""
    name = Path((filename or "").replace("\\", "/")).name
    stem = re.sub(r"[^A-Za-z0-9._-]", "_", Path(name).stem).strip("._") or "rfcv"
    return f"{stem[:100]}.pdf"


def _pdf_text(path: Path) -> str:
    with pdf_extractor.PDFExtractor(str(path)) as extractor:
        return extractor.extract_all_text() or ""


def _same_rfcv(a: Optional[str], b: Optional[str]) -> bool:
    na, nb = normalize_rfcv(a), normalize_rfcv(b)
    return bool(na) and na == nb


class DossierService:
    def __init__(self, conn: sqlite3.Connection, settings: WebappSettings, registry: ChassisRegistry):
        if registry is None:
            raise ValueError("Registre des châssis requis")
        self.conn = conn
        self.settings = settings
        self.registry = registry

    # -------------------------------------------------------------- lecture
    @property
    def _root(self) -> Path:
        return Path(self.settings.data_dir) / "dossiers"

    def get(self, dossier_id: int) -> dict:
        row = self.conn.execute("SELECT * FROM dossiers WHERE id = ?", (dossier_id,)).fetchone()
        if row is None:
            raise DossierIntrouvable(f"Dossier {dossier_id} introuvable")
        return dict(row)

    def generations(self, dossier_id: int) -> list[dict]:
        """Générations du dossier, la plus récente d'abord."""
        rows = self.conn.execute("SELECT * FROM generations WHERE dossier_id = ? ORDER BY n DESC",
                                 (dossier_id,)).fetchall()
        return [dict(r) for r in rows]

    def latest_summary(self, dossier_id: int) -> Optional[Summary]:
        row = self.conn.execute("SELECT summary_json FROM generations WHERE dossier_id = ? "
                                "AND summary_json IS NOT NULL ORDER BY n DESC LIMIT 1",
                                (dossier_id,)).fetchone()
        return Summary.from_dict(json.loads(row[0])) if row else None

    def _event(self, dossier_id: Optional[int], email: str, action: str, detail: str = "") -> None:
        self.conn.execute("INSERT INTO events (dossier_id, email, action, detail, at) VALUES (?, ?, ?, ?, ?)",
                          (dossier_id, email, action, detail or None, db.now_iso()))

    # -------------------------------------------------------------- création
    def create(self, user: User, filename: str, content: bytes) -> int:
        """Nouveau dossier en brouillon ; le n° RFCV est lu dans le PDF si possible."""
        if not content or not content.lstrip()[:5].startswith(b"%PDF"):
            raise ValueError(f"« {filename} » n'est pas un fichier PDF")
        safe = _safe_filename(filename)
        now = db.now_iso()
        folder = None
        try:
            cur = self.conn.execute(
                "INSERT INTO dossiers (filename, pdf_path, created_by, created_at) VALUES (?, '', ?, ?)",
                (safe, user.email, now))
            dossier_id = cur.lastrowid
            folder = self._root / str(dossier_id)
            self._set_aside_orphan(folder)
            folder.mkdir(parents=True, exist_ok=False)
            pdf_path = folder / safe
            pdf_path.write_bytes(content)
            rfcv_number = self._read_rfcv_number(pdf_path)
            self.conn.execute("UPDATE dossiers SET pdf_path = ?, rfcv_number = ? WHERE id = ?",
                              (str(pdf_path), rfcv_number, dossier_id))
            self._event(dossier_id, user.email, "creation", f"{safe} ({rfcv_number or 'n° RFCV illisible'})")
            self.conn.commit()
        except BaseException:
            self.conn.rollback()
            # l'id sera réattribué : ne pas laisser de dossier sur le disque
            if folder is not None and folder.exists():
                shutil.rmtree(folder, ignore_errors=True)
            raise
        return dossier_id

    @staticmethod
    def _set_aside_orphan(folder: Path) -> None:
        """
        Un dossier présent sur le disque pour un id tout juste attribué n'a pas de ligne en
        base (création interrompue, base restaurée) : il est mis de côté, jamais supprimé.
        """
        if not folder.exists():
            return
        stamp = db.now_iso().replace(":", "")
        target = folder.with_name(f"{folder.name}.orphelin-{stamp}")
        i = 1
        while target.exists():
            target = folder.with_name(f"{folder.name}.orphelin-{stamp}-{i}")
            i += 1
        logger.warning("Dossier orphelin %s mis de côté sous %s", folder, target.name)
        folder.rename(target)

    @staticmethod
    def _read_rfcv_number(pdf_path: Path) -> Optional[str]:
        try:
            m = RFCV_NUMBER.search(_pdf_text(pdf_path))
        except Exception as exc:  # PDF illisible : le dossier est créé quand même
            logger.warning("N° RFCV illisible dans %s : %s", pdf_path, exc)
            return None
        return m.group(0) if m else None

    # -------------------------------------------------------------- réglages proposés
    def default_settings(self, dossier_id: int) -> GenerationSettings:
        """Réglages proposés : dernier taux utilisé, profil société, Takikro, désignation courte."""
        dossier = self.get(dossier_id)
        row = self.conn.execute("SELECT settings_json FROM generations "
                                "ORDER BY created_at DESC, id DESC LIMIT 1").fetchone()
        taux = self.settings.default_taux
        if row:
            taux = float(json.loads(row[0]).get("taux_douane") or taux)

        profile = None
        profile_path = Path(self.settings.profile_path)
        if profile_path.exists():
            profile = load_profile(str(profile_path))
        else:
            logger.warning("Profil société introuvable : %s", profile_path)

        takikro, designation = False, None
        try:
            text = _pdf_text(Path(dossier["pdf_path"]))
            header = fmt.parse_header(text)
            takikro = header.get("country_code") == "TG" and header.get("transport_mode_code") == "3"
            items = fmt.parse_items(text)[0]
            if items:
                designation = suggest_designation(items[0]["description"])
        except Exception as exc:  # proposition seulement : l'utilisateur saisit les réglages
            logger.warning("Lecture du RFCV du dossier %s pour les réglages : %s", dossier_id, exc)
        return GenerationSettings(taux_douane=taux, profile=profile, takikro=takikro,
                                  designation=designation)

    # -------------------------------------------------------------- génération
    def _other_drafts(self, dossier_id: int) -> dict[str, set[str]]:
        out = {}
        rows = self.conn.execute("SELECT id, rfcv_number FROM dossiers WHERE status = 'brouillon' AND id != ?",
                                 (dossier_id,)).fetchall()
        for r in rows:
            summary = self.latest_summary(r["id"])
            if summary and summary.vins:
                out[f"RFCV {r['rfcv_number'] or '?'} (dossier {r['id']})"] = set(summary.vins)
        return out

    def _known_hs(self) -> Optional[set[tuple[str, str]]]:
        rows = self.conn.execute("SELECT designation, hs_code FROM hs_known").fetchall()
        return {(r[0], r[1]) for r in rows} or None

    def _next_n(self, dossier_id: int, folder: Path) -> int:
        n_db = self.conn.execute("SELECT COALESCE(MAX(n), 0) FROM generations WHERE dossier_id = ?",
                                 (dossier_id,)).fetchone()[0]
        n_disk = max((int(p.name[4:]) for p in folder.glob("gen-*") if p.name[4:].isdigit()), default=0)
        return max(n_db, n_disk) + 1

    def generate(self, user: User, dossier_id: int, settings: GenerationSettings) -> Optional[int]:
        """
        Nouvelle génération (n° renvoyé). Échec du moteur : message dans dossiers.error, None
        renvoyé, aucune exception. Dossier déclaré ou annulé : DossierFige.
        """
        dossier = self.get(dossier_id)
        if dossier["status"] in FIGES:
            raise DossierFige(f"Dossier {dossier_id} {'déclaré' if dossier['status'] == 'declare' else 'annulé'} : "
                              "il ne peut plus être régénéré")
        folder = self._root / str(dossier_id)
        n = self._next_n(dossier_id, folder)
        out_dir = folder / f"gen-{n}"
        stem = Path(dossier["filename"]).stem
        out_dir.mkdir(parents=True, exist_ok=False)
        try:
            result = generate_drafts(Path(dossier["pdf_path"]), settings, out_dir, stem, self.registry,
                                     other_drafts=self._other_drafts(dossier_id), known_hs=self._known_hs())
        except Exception as exc:
            logger.exception("Génération du dossier %s", dossier_id)
            shutil.rmtree(out_dir, ignore_errors=True)  # créé par cet appel : sorties partielles
            message = f"Échec de la génération : {exc}"
            self.conn.execute("UPDATE dossiers SET error = ? WHERE id = ?", (message, dossier_id))
            self._event(dossier_id, user.email, "generation_echec", message)
            self.conn.commit()
            return None
        try:
            self.conn.execute(
                "INSERT INTO generations (dossier_id, n, settings_json, summary_json, xml_path, corps_path, "
                "created_by, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (dossier_id, n, json.dumps(settings.to_dict(), ensure_ascii=False),
                 json.dumps(result.summary.to_dict(), ensure_ascii=False),
                 str(result.xml_path), str(result.corps_path), user.email, db.now_iso()))
            self.conn.execute("UPDATE dossiers SET error = NULL WHERE id = ?", (dossier_id,))
            self._event(dossier_id, user.email, "generation", f"génération {n}")
            self.conn.commit()
        except BaseException:
            self.conn.rollback()
            raise
        return n

    # -------------------------------------------------------------- déclaration
    def declare(self, user: User, dossier_id: int) -> None:
        """« Déclaré dans SYDAM » : enregistre les VIN de la dernière génération dans le registre."""
        with _declare_lock:
            self._declare(user, dossier_id)

    def _refuse(self, user: User, dossier_id: int, message: str, conflicts=None) -> None:
        self._event(dossier_id, user.email, "declaration_refusee", message)
        self.conn.commit()
        raise DeclarationRefusee(message, conflicts)

    def _declare(self, user: User, dossier_id: int) -> None:
        dossier = self.get(dossier_id)
        if dossier["status"] in FIGES:
            raise DossierFige(f"Dossier {dossier_id} déjà {'déclaré' if dossier['status'] == 'declare' else 'annulé'}")
        summary = self.latest_summary(dossier_id)
        if summary is None:
            self._refuse(user, dossier_id, "Aucune génération : générer le dossier avant de le déclarer")
        rfcv_number = dossier["rfcv_number"] or summary.rfcv_number
        # Un RFCV = une déclaration : un autre dossier du même RFCV déjà déclaré bloque.
        if normalize_rfcv(rfcv_number):
            autres = [r["id"] for r in self.conn.execute(
                "SELECT id, rfcv_number FROM dossiers WHERE status = 'declare' AND id != ?", (dossier_id,))
                if _same_rfcv(r["rfcv_number"], rfcv_number)]
            if autres:
                self._refuse(user, dossier_id,
                             f"Le RFCV {rfcv_number} est déjà déclaré par le dossier "
                             f"{', '.join(str(i) for i in autres)}. Un RFCV ne se déclare qu'une fois ; "
                             "un administrateur peut remettre ce dossier en brouillon si besoin.")

        conflicts, to_register = [], []
        for vin in dict.fromkeys(v.upper() for v in summary.vins):
            entry = self.registry.check_extracted(vin)
            if entry is None:
                to_register.append(vin)
            # entrée du même RFCV : reprise d'une tentative partielle de ce dossier (aucun
            # autre dossier de ce RFCV n'est déclaré, contrôlé ci-dessus) ; rien à écrire
            elif not _same_rfcv(entry.get("rfcv_number"), rfcv_number):
                conflicts.append({"chassis_number": vin, "rfcv_number": entry.get("rfcv_number"),
                                  "filename": entry.get("filename")})
        if conflicts:
            origines = sorted({c["rfcv_number"] or c["filename"] or "?" for c in conflicts})
            self._refuse(user, dossier_id,
                         f"{len(conflicts)} châssis déjà déclaré(s) par un autre dossier (RFCV d'origine : "
                         f"{', '.join(origines)}). Si ce RFCV a été annulé, un administrateur doit "
                         "enregistrer son annulation avant de déclarer ce dossier.", conflicts)
        bloquantes = [a.message for a in summary.alertes if a.bloquante]
        if bloquantes:
            self._refuse(user, dossier_id, "Alerte bloquante dans la dernière génération : "
                         + " ; ".join(bloquantes) + ". Corriger puis régénérer le dossier.")

        written = []
        try:
            for vin in to_register:
                self.registry.register_extracted(vin, dossier["filename"], rfcv_number)
                written.append(vin)
            now = db.now_iso()
            self.conn.execute("UPDATE dossiers SET status = 'declare', declared_by = ?, declared_at = ?, "
                              "error = NULL WHERE id = ?", (user.email, now, dossier_id))
            if summary.designation:
                self.conn.executemany("INSERT OR IGNORE INTO hs_known (designation, hs_code) VALUES (?, ?)",
                                      [(summary.designation, code) for code in summary.codes_sh])
            self._event(dossier_id, user.email, "declaration",
                        f"{len(written)} châssis enregistré(s), RFCV {rfcv_number or '?'}")
            self.conn.commit()
        except BaseException as exc:
            self.conn.rollback()
            for vin in written:
                try:
                    self.registry.delete(vin)
                except Exception:
                    logger.exception("Retrait du châssis %s après échec de déclaration", vin)
            if isinstance(exc, ValueError) and len(written) < len(to_register):
                # châssis enregistré entre le contrôle et l'écriture
                raise DeclarationRefusee(f"Déclaration interrompue : {exc}", []) from exc
            raise

    # -------------------------------------------------------------- retour en brouillon
    def revert_to_draft(self, admin: User, dossier_id: int) -> None:
        """Administrateur : dossier déclaré -> brouillon ; retire ses châssis du registre."""
        if not getattr(admin, "is_admin", False):
            raise PermissionError("Réservé aux administrateurs")
        dossier = self.get(dossier_id)
        if dossier["status"] != "declare":
            raise ValueError(f"Dossier {dossier_id} non déclaré : rien à remettre en brouillon")
        summary = self.latest_summary(dossier_id)
        rfcv_number = dossier["rfcv_number"] or (summary.rfcv_number if summary else None)
        removed = []
        for vin in (summary.vins if summary else []):
            entry = self.registry.check_extracted(vin)
            if entry and _same_rfcv(entry.get("rfcv_number"), rfcv_number):
                self.registry.delete(vin)
                removed.append(vin)
        self.conn.execute("UPDATE dossiers SET status = 'brouillon', declared_by = NULL, declared_at = NULL "
                          "WHERE id = ?", (dossier_id,))
        self._event(dossier_id, admin.email, "retour_brouillon", f"{len(removed)} châssis retiré(s) du registre")
        self.conn.commit()

    # -------------------------------------------------------------- liste
    def list(self, search: str | None = None) -> list[dict]:
        """Dossiers du plus récent au plus ancien ; recherche par n° RFCV (normalisé) ou VIN."""
        rows = self.conn.execute("SELECT * FROM dossiers ORDER BY created_at DESC, id DESC").fetchall()
        gens: dict[int, list[Summary]] = {}
        for g in self.conn.execute("SELECT dossier_id, summary_json FROM generations "
                                   "WHERE summary_json IS NOT NULL ORDER BY n DESC"):
            gens.setdefault(g[0], []).append(Summary.from_dict(json.loads(g[1])))

        q = (search or "").strip()
        q_vin, q_rfcv = re.sub(r"\s+", "", q).upper(), normalize_rfcv(q)
        out = []
        for r in rows:
            summaries = gens.get(r["id"], [])
            if q:
                rfcv_ok = bool(q_rfcv) and q_rfcv in normalize_rfcv(r["rfcv_number"])
                vin_ok = any(q_vin in v.upper() for s in summaries for v in s.vins)
                if not (rfcv_ok or vin_ok):
                    continue
            latest = summaries[0] if summaries else None
            out.append({
                "id": r["id"], "rfcv_number": r["rfcv_number"], "filename": r["filename"],
                "status": r["status"], "created_by": r["created_by"], "created_at": r["created_at"],
                "declared_at": r["declared_at"], "error": r["error"],
                "nb_articles": latest.nb_articles if latest else None,
                "fob_total": latest.fob_total if latest else None,
                "devise": latest.devise if latest else None,
            })
        return out
