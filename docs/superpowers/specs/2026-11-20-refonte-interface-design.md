# Refonte visuelle de la webapp de génération (identité Karta Transit)

Date : 2026-11-20 · Statut : à valider

## Intention

L'application interne (https://generation.karta-transit.ci) fonctionne en production, mais son interface est brute (une feuille de style de 37 lignes). L'équipe Karta l'utilise chaque jour : elle doit avoir une apparence moderne et professionnelle, aux couleurs de Karta Transit, sans changer ce que fait l'application.

Maquettes validées (canevas privé) : https://claude.ai/artifact/6i72YmcbiTJiQE4P6k1KK2 — écrans Dossiers, Fiche dossier, Génération (prototype interactif), Déposer des RFCV, Châssis.

## Objectifs

- Reproduire les maquettes validées sur les écrans existants : liste des dossiers, dépôt, fiche dossier (réglages, génération, récapitulatif, déclaration, historiques), Châssis.
- Mise en page « B » : menu latéral gris-blanc à gauche (logo, Dossiers, Déposer des RFCV, Châssis réservé aux administrateurs avec badge ADMIN, carte utilisateur en bas), contenu à droite.
- Parcours visible sur la fiche dossier : étapes 1. RFCV déposé → 2. Réglages et génération → 3. Vérification → 4. Déclaré dans SYDAM, dont l'état découle de l'état réel du dossier.
- États de génération clairs : pas encore généré, en cours (bouton désactivé + indicateur), réussie, échec, alerte bloquante, déclaré (figé), abandonné.
- Utilisable sur téléphone (menu qui passe au-dessus, tableaux qui défilent dans leur cadre).

## Non-objectifs

- Aucun changement de calcul, de route, de règle métier ni de format XML / corps.
- Authentification inchangée : Cloudflare Access (pas de Better Auth, pas de comptes locaux).
- Pas de framework JavaScript (pas de SvelteKit / Remix) : FastAPI + Jinja2 + htmx restent.
- Pas de progression détaillée de la génération (voir « Génération en cours »).

## Anti-objectifs (échec même si « ça marche »)

- Une interface qui dépend d'un service externe au chargement (CDN Tailwind, Google Fonts) : l'application doit s'afficher même si ces services sont injoignables.
- Une action qui disparaît ou change de sens (déclarer, abandonner, rouvrir, remettre en brouillon, annuler / restaurer un RFCV, marquer un code SH normal, téléchargements).
- Rouge de la marque confondu avec une erreur.

## Contraintes

- Tests existants (`tests/webapp/`) : ils vérifient des textes, des noms de champs, des liens et la présence / l'état désactivé du bouton « Déclaré dans SYDAM ». Les textes, `name=`, `id=` utilisés par htmx (`#recap`, `#erreurs-reglages`, `#generer`, `#declarer`, `#generation-en-cours`) et les routes restent ; un test ne s'adapte que si la maquette change un libellé, et le changement est listé dans la PR.
- Dépôt public : pas de données réelles. Le logo Karta Transit y entre comme fichier statique (choix assumé : c'est l'identité de l'application, déjà nommée dans les profils).
- Image Docker : la construction tourne sur la VM (Internet sortant disponible).
- Garde Access : `/static` reste derrière le garde, comme aujourd'hui.

## Approches envisagées

| Approche | Coût | Retenue |
|---|---|---|
| Tailwind sur la base actuelle (gabarits Jinja2 + htmx), CSS compilée | Gabarits à réécrire, une étape de compilation CSS ; rien d'autre ne bouge | **Oui** (choix de l'utilisateur) |
| SvelteKit en façade + API JSON | Deuxième service, API à créer pour chaque écran, double test | Non : coût élevé pour un gain d'interactivité non demandé |
| Remix / React | Idem, écosystème plus lourd | Non |

## Décisions (de l'utilisateur)

- Tailwind CSS, Cloudflare Access conservé.
- Identité Karta Transit, palette tirée du logo ; mise en page B.
- Menu latéral gris-blanc ; élément de menu actif sur fond bleu, sans liseré rouge.
- Bouton « Déclaré dans SYDAM » en vert.
- Écran de génération avec états et parcours en 4 étapes (prototype validé).

## Décisions de conception (mes choix, à corriger si besoin)

- **Compilation CSS** : Tailwind v4, CLI autonome (binaire unique, sans Node), version épinglée et somme SHA-256 vérifiée, exécutée dans une étape de construction du `Dockerfile` ; le CSS produit (`src/webapp/static/app.css`, minifié) est copié dans l'image. Pour le développement local : `scripts/css.sh` (télécharge le même binaire épinglé dans `.cache/`, compile, option `--watch`). Le fichier compilé n'est pas versionné (ajouté au `.gitignore`) ; les tests n'en dépendent pas.
- **Thème** (`src/webapp/styles/app.css`, entrée Tailwind avec `@theme`) :
  - bleu Karta `#1B1BA8` (actions, liens, menu actif), bleu nuit `#12127E` (titres, carte CIF), fond `#F4F5FB`, menu `#F7F8FB`, bordures `#E4E6F2`, texte `#161A3A` / secondaire `#5B6088` ;
  - rouge Karta `#FF2B52` : accents de marque seulement (avatar, badge) ;
  - succès `#0E8A45` (bouton déclarer, statut déclaré), avertissement ambre, erreur `#A3122E` sur fond `#FDECEF` toujours avec une icône.
  - Contraste texte ≥ 4,5:1.
- **Police** : Plus Jakarta Sans, auto-hébergée (`woff2` dans `static/fonts/`, licence OFL jointe), repli `system-ui`.
- **Icônes** : SVG en ligne (style trait), dans une macro Jinja `icone(nom)` ; pas d'emoji, pas de bibliothèque externe.
- **Composants Jinja** (`templates/_ui.html`, macros) : bouton (primaire, secondaire, succès, danger, désactivé), pastille de statut, carte de montant, alerte (succès / avertissement / erreur / bloquante), champ texte / montant / case, tableau. Les gabarits existants les utilisent ; pas de classes dupliquées dans chaque écran.
- **Fiche dossier** : en-tête (n° RFCV, statut, Takikro le cas échéant, méta, PDF d'origine), barre d'étapes, puis deux colonnes : réglages à gauche (tous les champs actuels, groupés « Déclaration » / « Valeurs », avec « par article (× N) »), état / récapitulatif à droite (`#recap`) : bandeau d'état, cartes FOB / fret / assurance / CIF, alertes, écarts, cases clés, téléchargements, bouton « Déclaré dans SYDAM ». Historique des générations et du dossier en bas.
- **Étapes** : calculées côté serveur à partir de l'état existant (aucune génération → étape 2 active ; dernière génération en échec → étape 2 en erreur ; génération OK → étape 3 active ; alerte bloquante → étape 3 en erreur ; déclaré → tout coché ; abandonné → bandeau gris, étapes grisées). Fonction pure testée.
- **Génération en cours** : la génération reste synchrone (une requête htmx d'environ 20 s pour 300 motos). Pendant la requête : bouton désactivé « Génération en cours… » avec rond qui tourne, et une barre d'attente animée dans `#recap` (indicateur htmx), avec la mention « environ 20 s pour 300 motos ». Pas d'étapes détaillées (lecture, châssis, XML, corps) : elles demanderaient de suivre la progression côté serveur ; laissé pour plus tard.
- **Liste des dossiers** : recherche (RFCV ou VIN), filtres par statut (liens `?statut=…` filtrant côté serveur — petit ajout de route : seul écart au « aucune route ne change », sans effet sur les existantes), tableau avec pastilles, ligne abandonnée grisée et barrée, état vide.
- **Dépôt** : zone de dépôt (le `<input type="file" multiple>` reste le vrai champ ; glisser-déposer natif sur le libellé), liste des fichiers choisis en JavaScript minimal, bouton « Créer N dossiers ».
- **Châssis** : recherche d'un VIN, formulaire d'annulation (cadre rouge), historique avec « Restaurer », formulaire « codes SH habituels » existant, même composants.
- **Confirmations** : les `confirm()` actuels restent (déclarer, abandonner, rouvrir, remettre en brouillon).
- **Accessibilité** : vrais `<button>`, `<a>`, `<label>` ; cibles ≥ 44 px ; `aria-live="polite"` sur `#recap` ; focus visible.

## Précisions (relecture avant plan, mes choix)

- **Maquettes et logo** : les maquettes restent sur le canevas privé (elles contiennent des n° RFCV et VIN réels : elles n'entrent pas dans ce dépôt public) ; le constructeur les lit depuis le canevas. Le logo (`LOGO-KARTA-TRANSIT.jpg` fourni par l'utilisateur) est ajouté en `src/webapp/static/img/logo-karta-transit.jpg` (redimensionné, ≤ 60 Ko).
- **Statuts et pastilles** : quatre statuts réels (`brouillon`, `declare`, `annule`, `abandonne`). Pastille affichée : Brouillon (bleu) si aucune génération réussie, **Généré** (ambre) si brouillon avec une génération réussie et sans erreur, Échec (rouge + icône) si la dernière tentative a échoué, Déclaré (vert), Annulé et Abandonné (gris, ligne grisée ; abandonné barré). Filtres : Tous (défaut, tous statuts comme aujourd'hui), Brouillons, Générés, Déclarés, Annulés / abandonnés. `?statut=` inconnu → Tous.
- **Étapes, ordre de priorité** (fonction pure, entrée : statut, dernière génération, erreur de la dernière tentative, alerte bloquante du récapitulatif) : 1) `declare` → tout coché ; 2) `abandonne` / `annule` → étapes grisées + bandeau ; 3) dernière tentative en échec (`dossier.error`) → étape 2 en erreur ; 4) aucune génération → étape 2 active ; 5) alerte bloquante (`summary.bloquante`) → étape 3 en erreur ; 6) sinon → étape 3 active. Un dossier remis en brouillon suit les mêmes règles (sa dernière génération décide).
- **htmx** : la barre d'étapes et le bandeau d'état sont rendus par `_recap.html` ; lors d'une réponse htmx, la barre d'étapes est envoyée en `hx-swap-oob` (même gabarit, aucune route modifiée) pour ne jamais rester périmée.
- **CSS en développement** : le seul déploiement réel est le `Dockerfile` (compose de production et `docker-compose.dev.yml` le construisent ; `render.yaml` n'est plus utilisé). `docker-compose.dev.yml` monte `./src` par-dessus l'image : en développement, lancer `scripts/css.sh` qui écrit `src/webapp/static/app.css` sur le disque. Si le fichier manque, la page reste utilisable (HTML sémantique) et un test d'intégration Docker vérifie qu'il est servi.
- **Libellés** : les libellés des maquettes l'emportent sur les anciens (« Nouveau » → « Déposer des RFCV », etc.) ; les textes des `confirm()` sont conservés ; les tests touchés sont adaptés et listés dans la PR.

## Reste au constructeur

- Découpage exact des macros et des classes Tailwind ; ajustements de mise en page fidèles aux maquettes.
- Version précise de Tailwind v4 (la plus récente stable au moment du travail) et sa somme SHA-256.
- Adaptation des tests à tout libellé modifié (liste dans la PR).

## Vérification

- `pytest tests/webapp` vert ; nouveaux tests : fonction des étapes (chaque état), filtre par statut, présence du lien CSS et des polices locales, aucune URL externe dans les gabarits.
- Construction Docker : le CSS est produit et servi (`/static/app.css` non vide).
- Contrôle visuel en local de chaque écran et de chaque état de génération, puis en production après accord.
