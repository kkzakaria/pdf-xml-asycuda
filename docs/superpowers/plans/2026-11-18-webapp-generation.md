# Webapp de génération XML et corps — plan de réalisation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal :** une application web interne où l'équipe opérationnelle de Karta dépose ses RFCV, règle chaque dossier, contrôle un récapitulatif, télécharge XML ASYCUDA et corps SYDAM, puis marque le dossier « Déclaré dans SYDAM ».

**Architecture :** le moteur de pdf-xml-asycuda gagne une fonction unique `generation.generate()` (brouillon, sans écriture dans le registre) et un résumé structuré ; un paquet `src/webapp/` (FastAPI + Jinja2 + htmx, SQLite) est monté dans l'application FastAPI existante ; tout est servi derrière Cloudflare Access (jeton vérifié par l'application), depuis un serveur local relié par Cloudflare Tunnel.

**Tech Stack :** Python 3.11, FastAPI, Jinja2, htmx 1.9.12 (fichier local, pas de CDN), `sqlite3` (bibliothèque standard), PyJWT[crypto], pytest + httpx, Docker Compose, `cloudflared`.

**Spec :** `docs/superpowers/specs/2026-11-18-webapp-generation-design.md`

## Global Constraints

- Langue de l'interface et des messages : français.
- Pour des réglages identiques, XML et corps **identiques octet pour octet** à `converter.py … --corps` (sortie de référence).
- Générer un brouillon **n'écrit jamais** dans le registre des châssis ; seul « Déclaré dans SYDAM » (ou l'option CLI explicite) y écrit.
- Les VIN viennent toujours du RFCV ; la génération de VIN n'apparaît pas dans l'interface.
- Unités : FOB et fret en **devise du RFCV**, assurance en **XOF** ; « par article » = même montant × nombre d'articles.
- Un fret imposé ou un FOB révisé recalcule l'assurance quand elle est « formule ».
- Toute requête HTTP (pages et `/api/…`) sans jeton Cloudflare Access valide est refusée (401), sauf `/api/v1/health` et le mode développement explicite `WEBAPP_DEV_USER`.
- Fichiers d'un dossier jamais écrasés : chaque génération a son propre dossier `gen-<n>/`.
- Tests : jamais le registre du dépôt `data/chassis_registry.db` ; toujours `ChassisRegistry(tmp_path / "r.db")`.
- Aucun PDF, XML ou corps réel commité (déjà ignorés par `.gitignore`).

## Review Focus

1. **Deux brouillons du même RFCV** (deux collègues, ou le même deux fois) : chacun voit l'autre en alerte « châssis dans un autre brouillon », aucun n'est bloqué avant la déclaration ; le second « Déclaré » est refusé. → test `test_declare_refuses_chassis_declared_by_other_dossier` (Task 7).
2. **PDF non RFCV ou illisible déposé** : le dossier est créé avec une erreur lisible, rien ne plante, l'écran Dossiers reste utilisable. → test `test_generate_unreadable_pdf_sets_error` (Task 7).
3. **FOB révisé alors que les FOB du RFCV diffèrent entre articles** (cas 6014629) : l'alerte « FOB attestés différents » est affichée et le mode de répartition choisi est rappelé dans le récapitulatif. → test `test_summary_mixed_fob_alert` (Task 4).
4. **Jeton Access expiré ou d'une autre audience** (lien partagé, session ancienne) : 401, pas de page partielle. → test `test_wrong_audience_rejected` (Task 6).
5. **Dossier déclaré puis RFCV annulé par un admin** : le dossier passe « Annulé », ses châssis sont libérés et un nouveau dossier qui les reprend peut être déclaré. → test `test_cancel_rfcv_marks_dossier_and_frees_chassis` (Task 9).

---

## Structure des fichiers

| Fichier | Rôle |
|---|---|
| `src/rfcv_parser.py` (modifié) | `register_chassis`, `fob_mode`, `fret_impose`, `assurance_imposee` |
| `src/designation.py` (nouveau) | désignation courte proposée et appliquée |
| `src/generation.py` (nouveau) | `GenerationSettings`, `generate()`, `GenerationResult` |
| `src/generation_summary.py` (nouveau) | `summarize()` : totaux, valeurs distinctes, écarts, alertes |
| `converter.py`, `src/batch_processor.py`, `src/api/services/conversion_service.py` (modifiés) | contrôle seul par défaut, `--enregistrer-chassis` |
| `src/webapp/__init__.py` | `create_router()` monté dans `src/api/main.py` |
| `src/webapp/config.py` | réglages `WEBAPP_*` |
| `src/webapp/auth.py` | vérification du jeton Access, utilisateur courant, rôles |
| `src/webapp/db.py` | schéma SQLite et accès |
| `src/webapp/dossiers.py` | cycle d'un dossier (créer, générer, déclarer, remettre en brouillon, annuler) |
| `src/webapp/routes.py` | pages et actions htmx |
| `src/webapp/templates/*.html`, `src/webapp/static/` | gabarits, `htmx.min.js`, `app.css` |
| `deploy/serveur/docker-compose.yml`, `deploy/serveur/INSTALLATION.md`, `deploy/serveur/sauvegarde.sh` | déploiement |

---

### Task 1 : Parseur — contrôle des châssis sans écriture

**Files :** Modify `src/rfcv_parser.py` (`__init__`, `_finalize`) · Test `tests/test_generation_engine.py`

**Interfaces :**
- Produces : `RFCVParser(..., register_chassis: bool = True)` ; attribut `parser.chassis_conflicts: list[dict]` (mêmes clés que `DuplicateChassisError.duplicates` : `chassis_number`, `first_seen_date`, `first_filename`, `first_rfcv_number`).

- [ ] **Step 1 : tests** (réutiliser `MULTILINE_TEXT` et `parse_text` de `tests/test_rfcv_format_2026.py`)

```python
def test_check_only_never_writes(registry, tmp_path):
    data = parse_text(MULTILINE_TEXT, registry, tmp_path, register_chassis=False)
    assert registry.get_all_extracted() == []

def test_check_only_reports_conflicts_instead_of_raising(registry, tmp_path):
    parse_text(MULTILINE_TEXT, registry, tmp_path)                       # enregistre (défaut)
    p = parse_text_parser(MULTILINE_TEXT.replace("RCSA6099999", "RCSA6099998"), registry, tmp_path,
                          register_chassis=False)                        # ne lève pas
    assert {c["first_rfcv_number"] for c in p.chassis_conflicts} == {"RCSA6099999"}
```
`parse_text_parser` : variante de `parse_text` qui rend le parseur après `parse()` (à ajouter dans le fichier de test).
- [ ] **Step 2 :** `pytest tests/test_generation_engine.py -k check_only -v` → FAIL (paramètre inconnu).
- [ ] **Step 3 :** dans `_finalize`, si `register_chassis` est faux : copier `_chassis_duplicates` dans `chassis_conflicts`, ne pas lever, ne rien enregistrer ; sinon comportement actuel.
- [ ] **Step 4 :** relancer → PASS ; `pytest tests/test_rfcv_format_2026.py tests/test_annulation_rfcv.py -q` → PASS.
- [ ] **Step 5 :** commit `feat(moteur): contrôle des châssis sans écriture (register_chassis)`.

### Task 2 : Parseur — FOB uniforme, fret et assurance imposés

**Files :** Modify `src/rfcv_parser.py` (`__init__`, `_apply_fob_revision`, `_finalize`) · Test `tests/test_generation_engine.py`

**Interfaces :**
- Produces : `RFCVParser(..., fob_mode: str = "prorata", fret_impose: float | None = None, assurance_imposee: float | None = None)`. `fob_mode` ∈ `{"prorata", "uniforme"}` (ValueError sinon) ; `fret_impose` = total en devise du RFCV ; `assurance_imposee` = total en XOF. Les deux montants > 0 sinon ValueError.

- [ ] **Step 1 : tests** (FOB RFCV 33 333,34 + 33 333,33 + 33 333,33, fret 3 000, XOF)

```python
def test_fob_uniform(registry, tmp_path):
    d = parse_text(MULTILINE_TEXT, registry, tmp_path, register_chassis=False, fob_revise=150000, fob_mode="uniforme")
    assert [i.tarification.item_price for i in d.items] == [50000.0, 50000.0, 50000.0]

def test_imposed_freight_and_insurance_per_article_reference_case(registry, tmp_path):
    # cas de référence 6014670 transposé : FOB 5 400, fret 2 000, assurance 93 par article
    d = parse_text(MULTILINE_TEXT, registry, tmp_path, register_chassis=False, taux_douane=1.0,
                   fob_revise=3 * 5400, fob_mode="uniforme", fret_impose=3 * 2000, assurance_imposee=3 * 93)
    vi = [i.valuation_item for i in d.items]
    assert [v.external_freight.amount_national for v in vi] == [2000.0] * 3
    assert [v.insurance.amount_national for v in vi] == [93.0] * 3
    assert [v.total_cif for v in vi] == [7493.0] * 3
    assert d.items[0].tarification.value_item == "2,000+0+93+0-0"

def test_imposed_freight_recomputes_formula_insurance(registry, tmp_path):
    d = parse_text(MULTILINE_TEXT, registry, tmp_path, register_chassis=False, taux_douane=1.0, fret_impose=10000)
    assert d.valuation.insurance.amount_national == math.ceil(2500 + (100000 + 10000) * 0.0015)
```
- [ ] **Step 2 :** lancer → FAIL.
- [ ] **Step 3 :** `fob_mode="uniforme"` : `distribute_evenly` (de `asycuda_enrichment`) sur les centimes au lieu du prorata ; `fret_impose` remplace `valuation.external_freight.amount_foreign` (et `amount_national` × taux) avant la répartition proportionnelle de `_finalize`, puis recalcule l'assurance si `_insurance_from_formula` ; `assurance_imposee` remplace `valuation.insurance` (XOF, taux 1) en dernier, avant `ProportionalCalculator().apply_to_rfcv`.
- [ ] **Step 4 :** relancer → PASS ; suite `tests/test_rfcv_format_2026.py` → PASS.
- [ ] **Step 5 :** commit `feat(moteur): FOB uniforme, fret et assurance imposés`.

### Task 3 : Désignation courte

**Files :** Create `src/designation.py` · Test `tests/test_designation.py`

**Interfaces :**
- Produces : `suggest_designation(raw: str | None) -> str | None` ; `apply_designation(rfcv_data: RFCVData, designation: str) -> int` (nombre d'articles modifiés ; écrit `item.packages.marks1` et `item.goods_description`).

- [ ] **Step 1 : tests**

```python
@pytest.mark.parametrize("raw,expected", [
    ("TRICYLE-APSONIC-", "TRICYCLE"), ("TRICYCLE - APSONIC -", "TRICYCLE"), ("TRICYCLE-APSONIC -", "TRICYCLE"),
    ("MOTO-APSONIC-", "MOTO"), ("MOTORCYCLE", "MOTO"), ("MOTO", None), ("TRICYCLE", None), ("PNEUS", None)])
def test_suggest(raw, expected):
    assert suggest_designation(raw) == expected

def test_apply_sets_marks_and_description():
    d = RFCVData(items=[Item(packages=Package(marks1="TRICYLE-APSONIC-"), goods_description="TRICYLE-APSONIC-")])
    assert apply_designation(d, "TRICYCLE") == 1
    assert (d.items[0].packages.marks1, d.items[0].goods_description) == ("TRICYCLE", "TRICYCLE")
```
`None` = déjà propre ou inconnu (rien à proposer).
- [ ] **Step 2 :** lancer → FAIL. **Step 3 :** implémenter (règles : mot commençant par `TRICY` → `TRICYCLE` ; `MOTO`/`MOTORCYCLE` suivi d'autre chose → `MOTO`). **Step 4 :** PASS.
- [ ] **Step 5 :** commit `feat(moteur): désignation courte proposée et appliquée`.

### Task 4 : `generate()` et résumé

**Files :** Create `src/generation.py`, `src/generation_summary.py` · Test `tests/test_generation.py`

**Interfaces :**
- Consumes : Tasks 1-3 ; `apply_profile` (`company_profile`), `XMLGenerator`, `generate_corps` (`corps_generator`).
- Produces :

```python
@dataclass
class Amount:
    value: float
    per_article: bool = False          # vrai : value × nombre d'articles

@dataclass
class GenerationSettings:
    taux_douane: float
    profile: CompanyProfile | None = None
    dossier: str | None = None
    manifeste: str | None = None
    nationalite_transport: str | None = None
    rapport_paiement: str | None = None
    takikro: bool = False
    disp: bool = False
    fob_revise: Amount | None = None
    fob_mode: str = "prorata"
    fret: Amount | None = None
    assurance_mode: str = "formule"     # "formule" | "rfcv" | "imposee"
    assurance: Amount | None = None     # requis si "imposee"
    designation: str | None = None
    def to_dict(self) -> dict: ...      # JSON, pour la base
    @classmethod
    def from_dict(cls, d: dict) -> "GenerationSettings": ...

@dataclass
class GenerationResult:
    xml_path: Path
    corps_path: Path
    summary: "Summary"

def generate(pdf_path: Path, settings: GenerationSettings, out_dir: Path, stem: str,
             registry: ChassisRegistry, other_drafts: dict[str, set[str]] | None = None) -> GenerationResult
```
`generate` parse une première fois pour connaître le nombre d'articles quand un montant est `per_article`, puis parse avec les totaux ; écrit `out_dir/<stem>.xml` et `out_dir/corps_<stem>.txt` ; `other_drafts` = {libellé du dossier : VIN} pour l'alerte « autre brouillon ».

```python
@dataclass
class Alert:
    code: str          # "chassis_declares", "chassis_autre_brouillon", "colis_zero", "somme_articles",
                       # "fob_heterogene", "designation", "code_sh_inhabituel"
    message: str       # français, prêt à afficher
    bloquante: bool    # vrai seulement pour "chassis_declares" et "somme_articles"

@dataclass
class Summary:
    rfcv_number: str | None; nb_articles: int; nb_vin: int
    fob_total: float; fret_total: float; assurance_total: float; cif_total: float
    colis: int; poids_brut: float; poids_net: float
    valeurs_articles: dict[str, list[tuple[float, int]]]   # "fob"/"fret"/"assurance"/"cif" -> [(valeur, nb)]
    cases: dict[str, str]                                   # Fcx_Aa, Fcx_29a, Fcx_10, Fcx_18b, Fcx_28b, Fcx_31f, Fld_40
    ecarts: list[str]                                        # écarts vs RFCV, en clair
    alertes: list[Alert]
    vins: list[str]
    designation: str | None; codes_sh: list[str]

def summarize(rfcv_data: RFCVData, rfcv_reference: RFCVData, corps: CorpsResult,
              conflicts: list[dict], other_drafts: dict[str, set[str]],
              known_hs: set[tuple[str, str]] | None) -> Summary
```
`rfcv_reference` = le même RFCV parsé sans aucun réglage (pour les écarts). `known_hs=None` désactive l'alerte code SH (registre vide).
- [ ] **Step 1 : tests** — `test_generate_matches_cli_output` (même PDF d'exemple `OT_M_2026_08746_BL_2026_07362_RFCV_v1.pdf`, réglages Takikro + DISP + taux 576.42 : octets identiques à `convert_pdf_to_xml(..., corps=True)` ; skip si PDF absent) ; `test_generate_never_writes_registry` ; `test_settings_roundtrip_dict` ; `test_per_article_amounts` (texte `MULTILINE_TEXT`, `Amount(93, True)` → total 279) ; `test_summary_mixed_fob_alert` (FOB articles différents + `fob_revise` → alerte `fob_heterogene` non bloquante) ; `test_summary_conflict_alert_is_blocking` ; `test_summary_other_draft_alert` ; `test_summary_ecarts` (FOB révisé, assurance imposée, désignation : trois lignes d'écart).
- [ ] **Step 2 :** lancer → FAIL. **Step 3 :** implémenter. **Step 4 :** PASS.
- [ ] **Step 5 :** commit `feat(moteur): generate() en brouillon et résumé structuré`.

### Task 5 : CLI et API en contrôle seul par défaut

**Files :** Modify `converter.py`, `src/batch_processor.py`, `src/api/services/conversion_service.py`, `tests/api/test_convert_duplicate.py`, `README.md`, `CLAUDE.md` · Test `tests/test_cli_registry_default.py`

**Interfaces :** Produces : option CLI `--enregistrer-chassis` ; `convert_pdf_to_xml(..., register_chassis: bool = False)`. Sans l'option, les doublons sont affichés en avertissement (RFCV d'origine), la conversion réussit.
- [ ] **Step 1 : tests** — `test_cli_default_does_not_register`, `test_cli_flag_registers`, `test_cli_flag_refuses_duplicate` (sous-processus avec `--db`… ou monkeypatch de `get_registry` sur un registre temporaire) ; adapter `test_convert_duplicate.py` : l'API ne renvoie plus 409 par défaut.
- [ ] **Step 2 :** FAIL. **Step 3 :** implémenter ; README (section registre) et CLAUDE.md : « conversion = contrôle seul ; enregistrement à la déclaration ». **Step 4 :** suite complète : pas plus d'échecs que les 40 connus de `main`.
- [ ] **Step 5 :** commit `feat: conversion en contrôle seul, enregistrement explicite des châssis`.

### Task 6 : Webapp — configuration, authentification Access, base

**Files :** Create `src/webapp/__init__.py`, `config.py`, `auth.py`, `db.py` ; Modify `src/api/main.py`, `requirements.txt` (`jinja2>=3.1`, `PyJWT[crypto]>=2.8`) · Test `tests/webapp/test_auth.py`, `tests/webapp/test_db.py`, `tests/webapp/conftest.py`

**Interfaces :**
- Produces :
  - `config.WebappSettings` (pydantic-settings, préfixe `WEBAPP_`) : `team_domain="groupekarta.cloudflareaccess.com"`, `access_aud: str`, `admins: list[str]`, `dev_user: str | None = None`, `data_dir: Path = Path("data/webapp")`, `registry_path: Path = Path("data/chassis_registry.db")`, `default_taux: float = 596.302`, `profile_path: Path = Path("profils/karta-transit.ini")`.
  - `auth.User(email: str, is_admin: bool)` ; dépendance FastAPI `current_user(request) -> User` (en-tête `Cf-Access-Jwt-Assertion` ou cookie `CF_Authorization` ; clés `https://<team_domain>/cdn-cgi/access/certs` mises en cache ; RS256, `aud` = `access_aud`, `iss` = `https://<team_domain>`) ; `require_admin`.
  - Middleware `access_guard` sur toute l'application (pages et `/api/…`, sauf `/api/v1/health`).
  - `db.connect(path) -> sqlite3.Connection` ; `db.init(conn)` crée : `users(email PK, first_seen, last_seen)`, `dossiers(id PK, rfcv_number, filename, pdf_path, status CHECK IN ('brouillon','declare','annule'), created_by, created_at, declared_by, declared_at, error)`, `generations(id PK, dossier_id, n, settings_json, summary_json, xml_path, corps_path, created_by, created_at)`, `hs_known(designation, hs_code, PK(designation, hs_code))`, `events(id PK, dossier_id NULL, email, action, detail, at)`.
- [ ] **Step 1 : tests** — jetons signés par une clé RSA de test (JWKS injecté) : `test_valid_token_gives_user`, `test_missing_token_401`, `test_wrong_audience_rejected`, `test_expired_token_rejected`, `test_admin_from_config`, `test_dev_user_mode`, `test_api_routes_also_guarded`, `test_health_open` ; `test_db_init_idempotent`.
- [ ] **Step 2 :** FAIL. **Step 3 :** implémenter ; monter le routeur webapp à `/` (la route racine JSON actuelle passe à `/api`), fichiers statiques à `/static`. **Step 4 :** PASS.
- [ ] **Step 5 :** commit `feat(webapp): authentification Cloudflare Access et base SQLite`.

### Task 7 : Webapp — cycle d'un dossier

**Files :** Create `src/webapp/dossiers.py` · Test `tests/webapp/test_dossiers.py`

**Interfaces :**
- Consumes : `generation.generate`, `GenerationSettings`, `Summary` (Task 4) ; `ChassisRegistry` ; `db` (Task 6).
- Produces : `class DossierService(conn, settings: WebappSettings, registry: ChassisRegistry)` avec
  - `create(user: User, filename: str, content: bytes) -> int` (PDF rangé sous `data_dir/dossiers/<id>/`, n° RFCV lu si possible) ;
  - `default_settings(dossier_id) -> GenerationSettings` (taux = dernier utilisé sinon `default_taux` ; Takikro proposé si routier venu du Togo ; désignation = `suggest_designation`) ;
  - `generate(user, dossier_id, settings) -> int` (n° de génération ; fichiers dans `dossiers/<id>/gen-<n>/` ; `other_drafts` = VIN des autres brouillons ; erreur → `dossiers.error` rempli, pas d'exception) ;
  - `declare(user, dossier_id) -> None` (dernière génération ; enregistre ses VIN ; `DeclarationRefusee(message, conflicts)` si un VIN est enregistré par un autre dossier ou si une alerte bloquante existe ; ajoute les paires (désignation, code SH) à `hs_known`) ;
  - `revert_to_draft(admin, dossier_id)` (retire ses VIN du registre) ;
  - `list(search: str | None) -> list[dict]` (recherche par n° RFCV ou VIN).
- [ ] **Step 1 : tests** — `test_generate_twice_never_registers`, `test_declare_registers_chassis`, `test_declare_refuses_chassis_declared_by_other_dossier`, `test_other_draft_alert_between_two_dossiers`, `test_generate_unreadable_pdf_sets_error`, `test_revert_to_draft_admin_only_and_frees_chassis`, `test_files_never_overwritten`, `test_events_logged`, `test_declared_dossier_cannot_be_regenerated` (figé : `generate` lève `DossierFige`). (PDF d'exemple du dépôt ; texte RFCV injecté comme dans `parse_text` pour les cas avec VIN.)
- [ ] **Step 2 :** FAIL. **Step 3 :** implémenter. **Step 4 :** PASS.
- [ ] **Step 5 :** commit `feat(webapp): cycle d'un dossier (brouillon, déclaration, retour)`.

### Task 8 : Webapp — écrans Dossiers, Nouveau, Dossier

**Files :** Create `src/webapp/routes.py`, `templates/base.html`, `dossiers.html`, `nouveau.html`, `dossier.html`, `_recap.html`, `static/htmx.min.js` (htmx 1.9.12), `static/app.css` · Test `tests/webapp/test_pages.py`

**Interfaces :** Consumes : `DossierService` (Task 7), `current_user` (Task 6). Produces : routes `GET /` (Dossiers), `GET|POST /nouveau` (dépôt multiple), `GET /dossiers/{id}`, `POST /dossiers/{id}/generer` (htmx : rend `_recap.html`), `GET /dossiers/{id}/fichiers/{gen}/{xml|corps|pdf}`, `POST /dossiers/{id}/declarer`, `POST /dossiers/{id}/brouillon` (admin).
- Formulaire de réglages = champs de `GenerationSettings` (§5.3 de la spec), montants avec case « par article ». Récapitulatif = `Summary` : totaux, valeurs par article (« 300 × 43 101 »), cases clés, écarts, alertes (bloquantes en rouge, bouton « Déclaré dans SYDAM » désactivé tant qu'il y en a).
- [ ] **Step 1 : tests** (client httpx avec `WEBAPP_DEV_USER`) — `test_upload_two_pdfs_creates_two_dossiers`, `test_generate_shows_recap_values`, `test_download_corps_is_text_with_filename`, `test_declare_button_disabled_with_blocking_alert`, `test_operator_cannot_revert`, `test_search_by_vin`.
- [ ] **Step 2 :** FAIL. **Step 3 :** implémenter. **Step 4 :** PASS.
- [ ] **Step 5 :** commit `feat(webapp): écrans dossiers, dépôt et récapitulatif`.

### Task 9 : Webapp — écran Châssis (admin)

**Files :** Modify `src/webapp/routes.py`, `src/webapp/dossiers.py` ; Create `templates/chassis.html` · Test `tests/webapp/test_chassis_admin.py`

**Interfaces :** Produces : `GET /chassis` (recherche VIN : registre actif, annulations, dossier lié), `POST /chassis/annuler` (n° RFCV, motif → `registry.cancel_rfcv` ; dossiers déclarés de ce RFCV passent « annule »), `POST /chassis/restaurer/{rfcv}`, `POST /chassis/code-sh-normal` (ajoute à `hs_known`).
- [ ] **Step 1 : tests** — `test_cancel_rfcv_marks_dossier_and_frees_chassis`, `test_restore_conflict_shown`, `test_operator_forbidden_403`, `test_mark_hs_known_silences_alert`.
- [ ] **Step 2 :** FAIL. **Step 3 :** implémenter. **Step 4 :** PASS.
- [ ] **Step 5 :** commit `feat(webapp): écran châssis et annulation de RFCV`.

### Task 10 : Déploiement sur le serveur

**Files :** Modify `Dockerfile` (gabarits et statiques inclus, volume `/app/data`) ; Create `deploy/serveur/docker-compose.yml` (services `app` et `cloudflared`, réseau interne, aucun port publié), `deploy/serveur/.env.exemple` (`WEBAPP_ACCESS_AUD`, `WEBAPP_ADMINS`, `TUNNEL_TOKEN`), `deploy/serveur/sauvegarde.sh` (copie à chaud SQLite via `sqlite3 .backup` + archive des fichiers, rétention 30 jours), `deploy/serveur/INSTALLATION.md` · Test `tests/test_deploy_files.py`

**Interfaces :** INSTALLATION.md couvre, dans l'ordre : VM ou LXC Debian sur Proxmox avec Docker ; création du tunnel et du nom d'hôte `generation.karta-transit.ci` dans le compte Cloudflare Karta ; application Access (équipe Zero Trust `groupekarta.cloudflareaccess.com`, politique = e-mails de l'équipe) et récupération de l'AUD ; `.env` ; `docker compose up -d` ; tâche cron de `sauvegarde.sh` ; arrêt de l'instance Render (`render.yaml` conservé, service supprimé dans le tableau de bord).
- [ ] **Step 1 : test** — `test_compose_publishes_no_port` et `test_env_example_lists_required_vars` (lecture YAML/texte).
- [ ] **Step 2 :** FAIL. **Step 3 :** écrire les fichiers ; `docker compose -f deploy/serveur/docker-compose.yml config` valide. **Step 4 :** PASS ; image construite localement et `curl -H "Cf-Access-…"` absent → 401 sur `/`.
- [ ] **Step 5 :** commit `feat(deploiement): serveur local, tunnel et sauvegarde`.
