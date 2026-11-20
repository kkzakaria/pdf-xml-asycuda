# Refonte visuelle de la webapp — plan de réalisation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Donner à la webapp de génération l'apparence des maquettes validées (identité Karta Transit, mise en page B) avec Tailwind, sans changer ce qu'elle fait.

**Architecture:** Les gabarits Jinja2 de `src/webapp/templates` sont réécrits avec des classes Tailwind et des macros communes (`_ui.html`). Le CSS est compilé par le CLI autonome Tailwind v4 (étape du `Dockerfile`, script `scripts/css.sh` en local) depuis `src/webapp/styles/app.css` vers `src/webapp/static/app.css` (non versionné). Deux petites fonctions Python pures calculent la pastille de statut et la barre d'étapes ; un filtre `?statut=` s'ajoute à la liste.

**Tech Stack:** Python 3.11, FastAPI, Jinja2, htmx (déjà présent), Tailwind CSS v4 (CLI autonome, sans Node), pytest + httpx.

**Spec:** `docs/superpowers/specs/2026-11-20-refonte-interface-design.md` (maquettes : https://claude.ai/artifact/6i72YmcbiTJiQE4P6k1KK2, à lire avec l'outil Artifact, action `read`, chemins `project/Main.dc.html`, `project/Dossier.dc.html`, `project/Generation.dc.html`, `project/Nouveau.dc.html`, `project/Chassis.dc.html`).

## Global Constraints

- Aucun changement de calcul, de règle métier, de format XML / corps, d'authentification (Cloudflare Access) ; routes existantes inchangées (seul ajout : paramètre `statut` de `GET /`).
- Aucune ressource externe au chargement : pas de CDN, pas de Google Fonts ; police Plus Jakarta Sans auto-hébergée (`woff2`, licence OFL jointe), repli `system-ui`.
- Couleurs : bleu Karta `#1B1BA8` (actions, liens, menu actif), bleu nuit `#12127E` (titres, carte CIF), fond `#F4F5FB`, menu `#F7F8FB`, bordures `#E4E6F2`, texte `#161A3A`, secondaire `#5B6088`, rouge Karta `#FF2B52` (accents de marque seulement), succès `#0E8A45`, erreur `#A3122E` sur `#FDECEF` toujours avec icône, avertissement ambre (`#8A4B00` sur `#FFF3E0`).
- Menu latéral gris-blanc, élément actif fond bleu texte blanc, sans liseré rouge ; bouton « Déclaré dans SYDAM » vert.
- Conserver : ids htmx `#reglages`, `#recap`, `#erreurs-reglages`, `#generer`, `#declarer`, `#generation-en-cours` ; tous les `name=` de formulaire ; textes des `confirm()` ; `HX-Retarget`/`HX-Reswap` existants.
- Libellés des maquettes prioritaires (ex. « Nouveau » → « Déposer des RFCV ») ; tout test adapté est listé dans la PR.
- Dépôt public : aucune donnée réelle (pas de n° RFCV / VIN réels dans les tests ou exemples) ; logo ajouté en `src/webapp/static/img/logo-karta-transit.jpg` (≤ 60 Ko) depuis `/mnt/c/Users/SUPER/OneDrive/Desktop/LOGO-KARTA-TRANSIT.jpg`.
- Accessibilité : vrais `<button>`/`<a>`/`<label>`, cibles ≥ 44 px, contraste texte ≥ 4,5:1, `aria-live="polite"` sur `#recap`, `aria-current="page"` sur le menu actif, focus visible.
- Tests : `pytest tests/webapp` doit rester vert à chaque tâche ; venv de travail `/tmp/claude-1000/-home-super-takikro/20999819-b4eb-4870-b252-8eb22bf40a73/scratchpad/venv/bin/python -m pytest`.

## Review Focus

1. Erreurs de saisie pendant une génération htmx (taux invalide) : le formulaire se réaffiche dans `#reglages` avec les erreurs, le récapitulatif n'est pas écrasé — test dans la tâche 6.
2. Bouton « Déclaré dans SYDAM » : désactivé (et libellé d'explication visible) quand aucune génération, échec, alerte bloquante ou RFCV illisible ; absent quand le dossier est figé — test dans la tâche 6.
3. Dossier abandonné ou annulé ouvert directement : bandeau gris, étapes grisées, aucun formulaire de génération ; actions admin (rouvrir, remettre en brouillon) toujours là — test dans la tâche 6.
4. `?statut=` inconnu ou vide, combiné à une recherche `q` : liste complète filtrée par `q` seulement — test dans la tâche 4.
5. Page servie sans `app.css` compilé (tests, développement) : HTML lisible, aucun lien vers un domaine externe — test dans la tâche 1.

---

### Task 1: Chaîne CSS, police et logo

**Files:**
- Create: `src/webapp/styles/app.css` (entrée Tailwind), `scripts/css.sh`, `src/webapp/static/fonts/PlusJakartaSans-*.woff2` + `src/webapp/static/fonts/OFL.txt`, `src/webapp/static/img/logo-karta-transit.jpg`, `tests/webapp/test_ressources.py`
- Modify: `Dockerfile`, `.gitignore` (ajouter `src/webapp/static/app.css` et `.cache/`), `.dockerignore` (ne pas exclure `src/webapp/styles`), `src/webapp/templates/base.html` (lien CSS seulement)
- Delete: l'ancien `src/webapp/static/app.css` versionné (`git rm --cached`)

**Interfaces:**
- Produces: `/static/app.css` (compilé), `/static/fonts/…`, `/static/img/logo-karta-transit.jpg` ; tokens Tailwind `@theme` : `--color-karta-bleu: #1B1BA8`, `--color-karta-nuit: #12127E`, `--color-karta-rouge: #FF2B52`, `--color-fond: #F4F5FB`, `--color-menu: #F7F8FB`, `--color-bord: #E4E6F2`, `--color-encre: #161A3A`, `--color-encre-2: #5B6088`, `--color-succes: #0E8A45`, `--color-erreur: #A3122E`, `--color-erreur-fond: #FDECEF`, `--font-sans: "Plus Jakarta Sans", system-ui, sans-serif` (classes `bg-karta-bleu`, `text-encre-2`, etc.).

- [ ] **Step 1: Tests** dans `tests/webapp/test_ressources.py` :
  - `test_templates_sans_url_externe` : aucun fichier de `src/webapp/templates/` ne contient `http://` ou `https://` (hors `xmlns`).
  - `test_base_lie_css_local` : `GET /` (utilisateur de test) contient `href="/static/app.css"` et pas `fonts.googleapis`.
  - `test_logo_et_polices_servis` : `GET /static/img/logo-karta-transit.jpg` → 200, `image/jpeg` ; `GET /static/fonts/OFL.txt` → 200.
  - `test_entree_tailwind_declare_le_theme` : `src/webapp/styles/app.css` contient `@import "tailwindcss"`, `--color-karta-bleu: #1B1BA8` et `@source "../templates"`.
- [ ] **Step 2:** lancer `pytest tests/webapp/test_ressources.py -v` → échecs attendus (fichiers absents).
- [ ] **Step 3:** écrire `src/webapp/styles/app.css` : `@import "tailwindcss";`, `@source "../templates";`, `@theme { … }` (tokens ci-dessus), `@font-face` Plus Jakarta Sans (poids 400 à 800, `font-display: swap`, `url("/static/fonts/…")`), base (`body` fond `--color-fond`, couleur `--color-encre`), animation de la barre d'attente (`@keyframes avance`) et classe `.htmx-indicator` (masquée sauf pendant `.htmx-request`).
- [ ] **Step 4:** polices : variable `woff2` latin de Plus Jakarta Sans depuis le dépôt officiel (github.com/tokotype/PlusJakartaSans, OFL), copier `OFL.txt`. Logo : copier la source, la redimensionner à 400 px de large, JPEG qualité 85 (≤ 60 Ko).
- [ ] **Step 5:** `scripts/css.sh [--watch]` : télécharge dans `.cache/tailwindcss-<version>` le binaire `tailwindcss-linux-x64` de la version v4 stable épinglée (variable `TAILWIND_VERSION` et `TAILWIND_SHA256` en tête du script), vérifie la somme (`sha256sum -c`), puis `tailwindcss -i src/webapp/styles/app.css -o src/webapp/static/app.css --minify`. `set -euo pipefail`, échec si la somme diffère.
- [ ] **Step 6:** `Dockerfile` : étape `FROM debian:bookworm-slim AS css` qui copie `scripts/css.sh` et `src/webapp/`, lance le script, puis l'étape finale fait `COPY --from=css /build/src/webapp/static/app.css /app/src/webapp/static/app.css` après le `COPY src/`.
- [ ] **Step 7:** `bash scripts/css.sh` puis `pytest tests/webapp -q` → tout vert ; `docker build -t generation-test .` → réussit et `docker run --rm generation-test test -s /app/src/webapp/static/app.css` → code 0.
- [ ] **Step 8: Commit** `feat(webapp): chaîne CSS Tailwind, police et logo Karta`.

### Task 2: Gabarit commun et composants

**Files:**
- Create: `src/webapp/templates/_ui.html`, `src/webapp/templates/_icones.html`
- Modify: `src/webapp/templates/base.html`, `src/webapp/routes.py` (passer `active`), `tests/webapp/test_pages.py`

**Interfaces:**
- Consumes: tokens de la tâche 1.
- Produces (macros Jinja, `{% import "_ui.html" as ui %}`) : `ui.bouton(libelle, type="submit", variante="primaire"|"secondaire"|"succes"|"danger", id=None, disabled=False, icone=None, attrs="")`, `ui.lien_bouton(href, libelle, variante, icone=None)`, `ui.pastille(code, libelle)` (codes : `brouillon`, `genere`, `echec`, `declare`, `annule`, `abandonne`), `ui.alerte(niveau, titre, corps=None)` (`succes`|`avertissement`|`erreur`|`info`), `ui.carte_montant(libelle, valeur, detail, sombre=False)`, `ui.champ(name, label, value, hint=None, required=False, inputmode=None)`, `ui.case(name, label, checked)` ; `{% import "_icones.html" as ic %}` : `ic.icone(nom, taille=18)` pour `dossier`, `depot`, `chassis`, `recherche`, `plus`, `telecharger`, `valider`, `alerte`, `erreur`, `retour`, `regenerer`, `fichier`, `croix` (SVG trait `currentColor`, `aria-hidden="true"`).
- Produces : variable de gabarit `active` ∈ {`dossiers`, `nouveau`, `chassis`} passée par chaque route via `_render`.

- [ ] **Step 1: Tests** (dans `test_pages.py`) :
  - `test_menu_lateral` : `GET /` contient le logo `/static/img/logo-karta-transit.jpg`, les liens `/`, `/nouveau` (« Déposer des RFCV »), l'e-mail de l'utilisateur, et le lien Dossiers porte `aria-current="page"`.
  - `test_menu_chassis_admin_seulement` : opérateur → pas de lien `/chassis` ni « ADMIN » ; administrateur → lien `/chassis` et badge « ADMIN ».
- [ ] **Step 2:** lancer ces tests → échec.
- [ ] **Step 3:** `base.html` en mise en page B (maquette `Main.dc.html`) : `<aside>` gris-blanc (logo, sur-titre « Génération XML & corps », trois liens, carte utilisateur avec initiales sur fond rouge Karta, nom = partie locale de l'e-mail, « Administrateur » / « Opérateur »), `<main>` ; `flex-wrap` pour passer le menu au-dessus sur téléphone ; bandeau `#erreur-reseau` et script htmx existants conservés.
- [ ] **Step 4:** macros `_ui.html` et `_icones.html` (style des maquettes) ; `_render` ajoute `active`.
- [ ] **Step 5:** `pytest tests/webapp -q` → vert (adapter les libellés touchés).
- [ ] **Step 6: Commit** `feat(webapp): mise en page Karta et composants communs`.

### Task 3: Statut affiché et étapes du dossier

**Files:**
- Create: `src/webapp/presentation.py`, `tests/webapp/test_presentation.py`

**Interfaces:**
- Produces:
  - `statut_affiche(status: str, has_generation: bool, error: str | None) -> tuple[str, str]` → (code de pastille, libellé).
  - `@dataclass(frozen=True) class Etape: numero: int; libelle: str; etat: str` (`etat` ∈ `fait`, `actif`, `erreur`, `a_faire`, `inactif`).
  - `etapes_dossier(status: str, has_generation: bool, error: str | None, bloquante: bool) -> list[Etape]` (4 étapes : « RFCV déposé », « Réglages et génération », « Vérification », « Déclaré dans SYDAM »).

- [ ] **Step 1: Tests** :
  - `statut_affiche` : (`brouillon`, False, None) → (`brouillon`, « Brouillon ») ; (`brouillon`, True, None) → (`genere`, « Généré ») ; (`brouillon`, True, "x") → (`echec`, « Échec ») ; (`brouillon`, False, "x") → (`echec`, « Échec ») ; (`declare`, True, None) → (`declare`, « Déclaré ») ; (`annule`, True, None) → (`annule`, « Annulé ») ; (`abandonne`, False, None) → (`abandonne`, « Abandonné »).
  - `etapes_dossier`, états des étapes 1 à 4 dans l'ordre de priorité de la spec :
    - `declare` → `[fait, fait, fait, fait]`
    - `abandonne` (ou `annule`) → `[fait, inactif, inactif, inactif]`
    - `brouillon`, erreur → `[fait, erreur, a_faire, a_faire]`
    - `brouillon`, pas de génération → `[fait, actif, a_faire, a_faire]`
    - `brouillon`, génération, bloquante → `[fait, fait, erreur, a_faire]`
    - `brouillon`, génération OK → `[fait, fait, actif, a_faire]`
    - erreur ET bloquante → l'erreur l'emporte (`[fait, erreur, a_faire, a_faire]`).
- [ ] **Step 2:** `pytest tests/webapp/test_presentation.py -v` → échec (module absent).
- [ ] **Step 3:** implémenter dans `presentation.py` ; enregistrer `statut_affiche` et `etapes_dossier` comme globales Jinja dans `routes.py`.
- [ ] **Step 4:** tests → PASS.
- [ ] **Step 5: Commit** `feat(webapp): statut affiché et étapes du dossier`.

### Task 4: Liste des dossiers et filtre par statut

**Files:**
- Modify: `src/webapp/dossiers.py` (`DossierService.list`), `src/webapp/routes.py` (`dossiers`), `src/webapp/templates/dossiers.html`, `tests/webapp/test_dossiers.py`, `tests/webapp/test_pages.py`

**Interfaces:**
- Consumes: `statut_affiche` (tâche 3), macros (tâche 2).
- Produces: `DossierService.list(search: str | None = None, statut: str | None = None) -> list[dict]` ; chaque élément gagne `has_generation: bool` ; `FILTRES_STATUT = {"brouillon": "Brouillons", "genere": "Générés", "declare": "Déclarés", "clos": "Annulés / abandonnés"}` (`genere` = brouillon avec génération et sans erreur ; `brouillon` = brouillon sans génération réussie ou en échec ; `clos` = `annule` + `abandonne`) ; valeur inconnue ou vide → aucun filtre.

- [ ] **Step 1: Tests** :
  - `test_list_filtre_statut` (service) : avec un brouillon sans génération, un brouillon généré, un déclaré, un abandonné (données fictives) : `statut="genere"` → seulement le généré ; `"clos"` → l'abandonné ; `"inconnu"` → les quatre.
  - `test_list_filtre_et_recherche` : `search` + `statut` se combinent.
  - `test_page_filtres` (page) : `GET /?statut=declare` → le lien du filtre « Déclarés » porte `aria-current="true"` ; `GET /?statut=zzz` → 200 et tous les dossiers.
  - `test_page_vide` : aucun dossier → texte « Aucun dossier » et lien `/nouveau`.
- [ ] **Step 2:** tests → échec.
- [ ] **Step 3:** service + route (`statut: str = ""`) ; `dossiers.html` selon `Main.dc.html` : titre, recherche (`name="q"`, garde `statut` en champ caché), bouton « Déposer des RFCV », filtres en liens `?statut=…&q=…`, tableau (RFCV + fichier, déposé le + par, pastille `ui.pastille(*statut_affiche(...))`, articles, FOB + devise) dans un cadre `overflow-x-auto`, ligne abandonnée grisée et barrée, annulée grisée.
- [ ] **Step 4:** `pytest tests/webapp -q` → vert.
- [ ] **Step 5: Commit** `feat(webapp): liste des dossiers aux couleurs Karta, filtre par statut`.

### Task 5: Dépôt des RFCV

**Files:**
- Create: `src/webapp/static/depot.js`
- Modify: `src/webapp/templates/nouveau.html`, `tests/webapp/test_pages.py`

**Interfaces:**
- Consumes: macros (tâche 2).
- Produces: `depot.js` (chargé avec `defer`) : liste les fichiers choisis sous la zone et met à jour le bouton « Créer N dossier(s) » ; sans JavaScript, le formulaire fonctionne tel quel.

- [ ] **Step 1: Test** `test_page_depot` : `GET /nouveau` contient `type="file"`, `name="fichiers"`, `multiple`, `accept="application/pdf,.pdf"`, « Glissez vos PDF RFCV ici », `/static/depot.js`.
- [ ] **Step 2:** test → échec.
- [ ] **Step 3:** `nouveau.html` selon `Nouveau.dc.html` : `<label for="fichiers">` en zone de dépôt (le champ fichier reste dedans, visuellement masqué mais focusable), liste `#fichiers-choisis`, bouton `submit`, erreurs et dossiers créés via `ui.alerte`.
- [ ] **Step 4:** `pytest tests/webapp -q` → vert.
- [ ] **Step 5: Commit** `feat(webapp): écran de dépôt des RFCV`.

### Task 6: Fiche dossier, génération et déclaration

**Files:**
- Create: `src/webapp/templates/_etapes.html`
- Modify: `src/webapp/templates/dossier.html`, `_reglages.html`, `_recap.html`, `src/webapp/routes.py` (contexte : `has_generation`, `bloquante`), `tests/webapp/test_pages.py`

**Interfaces:**
- Consumes: `etapes_dossier`, `statut_affiche` (tâche 3), macros (tâche 2).
- Produces: `_etapes.html` rend `<ol id="etapes" aria-label="Étapes du dossier">` ; `_recap.html`, en réponse htmx, inclut aussi `_etapes.html` avec `hx-swap-oob="true"`.

- [ ] **Step 1: Tests** :
  - `test_fiche_etapes_avant_generation` : nouveau dossier → `id="etapes"`, l'étape « Réglages et génération » marquée active (`data-etat="actif"`), texte « Pas encore généré ».
  - `test_generation_htmx_met_a_jour_etapes` : POST `/dossiers/{id}/generer` avec `HX-Request: true` → la réponse contient `id="recap"`, `id="etapes"` avec `hx-swap-oob="true"` et « Vérification » `data-etat="actif"`.
  - `test_generation_erreur_saisie_htmx` (Review Focus 1) : taux « abc » en htmx → en-tête `HX-Retarget: #reglages`, réponse contenant le message d'erreur et pas `id="recap"`.
  - `test_bouton_declarer_desactive` (Review Focus 2) : sans génération → `#declarer` `disabled` + « Générer le dossier avant de le déclarer » ; après génération OK → actif, classe de variante succès.
  - `test_dossier_abandonne` (Review Focus 3) : abandonné → bandeau « Brouillon abandonné », pas de `id="generer"`, étapes `data-etat="inactif"` ; admin voit « Rouvrir le dossier ».
  - `test_indicateur_generation` : la fiche contient `id="generation-en-cours"` (classe `htmx-indicator`) et le texte « environ 20 s pour 300 motos ».
- [ ] **Step 2:** tests → échec.
- [ ] **Step 3:** `dossier.html` selon `Dossier.dc.html` et `Generation.dc.html` : retour « Tous les dossiers », en-tête (RFCV, pastille, Takikro si `summary.cases.Fcx_Aa == "CITKK"`, méta, PDF d'origine), `_etapes.html`, deux colonnes (`#reglages` à gauche, `#recap` à droite avec `aria-live="polite"`), historiques en bas, actions admin et abandon via `ui.bouton` (variante danger / secondaire) avec les `confirm()` actuels.
- [ ] **Step 4:** `_reglages.html` : groupes « Déclaration » / « Valeurs » en grille 2-3 colonnes, mêmes `name=`, « par article (× N) », bouton `#generer` (« Générer » ou « Régénérer »), `#generation-en-cours` : rond qui tourne + barre animée + « Génération en cours… environ 20 s pour 300 motos » ; `hx-disabled-elt="#generer"` conservé.
- [ ] **Step 5:** `_recap.html` : bandeau d'état (pas encore généré / réussie avec contrôles / échec / bloquant via `ui.alerte`), cartes FOB / fret / assurance / CIF (`ui.carte_montant`, CIF sombre, « par article » sous chaque total), alertes (dont le bouton admin « Marquer ce code SH comme normal »), écarts, cases clés, téléchargements XML / corps / PDF, formulaire `#declarer` vert avec ses messages, historiques ; en htmx, `{% include "_etapes.html" %}` avec `hx-swap-oob="true"`.
- [ ] **Step 6:** `pytest tests/webapp -q` → vert.
- [ ] **Step 7: Commit** `feat(webapp): fiche dossier, génération et déclaration aux couleurs Karta`.

### Task 7: Écran Châssis

**Files:**
- Modify: `src/webapp/templates/chassis.html`, `tests/webapp/test_chassis_admin.py`

**Interfaces:**
- Consumes: macros (tâche 2).

- [ ] **Step 1: Test** `test_chassis_mise_en_page` (admin) : `GET /chassis` contient les formulaires `action="/chassis/annuler"` (`name="rfcv"`, `name="motif"`) et la recherche `name="vin"`, le titre « Historique des annulations » ; les tests existants (annuler, restaurer, code SH normal) restent verts.
- [ ] **Step 2:** test → échec.
- [ ] **Step 3:** `chassis.html` selon `Chassis.dc.html` : deux cartes (recherche d'un VIN avec résultat registre / historique / dossiers ; annulation en cadre rouge), tableau d'historique avec « Restaurer » (formulaires existants), section codes SH habituels existante, messages via `ui.alerte`.
- [ ] **Step 4:** `pytest tests/webapp -q` → vert.
- [ ] **Step 5: Commit** `feat(webapp): écran Châssis aux couleurs Karta`.

### Task 8: Vérification finale et PR

- [ ] **Step 1:** `pytest -q` (suite complète) : mêmes échecs préexistants que `main` (40, codes 6022/6122 et assurance), aucun nouveau.
- [ ] **Step 2:** `bash scripts/css.sh`, lancer l'app en local avec `WEBAPP_DEV_USER` (données fictives), contrôler chaque écran et chaque état (avant, en cours, réussie, échec, bloquant, déclaré, abandonné) à 1440 px et 390 px ; corriger les écarts aux maquettes.
- [ ] **Step 3:** `docker build` → réussit, `/static/app.css` non vide dans l'image.
- [ ] **Step 4:** mettre à jour `deploy/serveur/INSTALLATION.md` (« Mettre à jour » : la construction compile le CSS) et le README de développement (`scripts/css.sh`).
- [ ] **Step 5:** commit, push de `feat/refonte-interface`, PR (liste des libellés et tests modifiés) — avec l'accord de l'utilisateur.
