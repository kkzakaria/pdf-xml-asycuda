# Webapp de génération XML ASYCUDA et corps SYDAM — conception

Date : 18/11/2026. Statut : à valider.

## 1. Intention

Aujourd'hui, chaque dossier (RFCV → XML ASYCUDA → corps SYDAM) passe par l'équipe outils
(le responsable et Claude), en ligne de commande, avec des réglages au cas par cas : FOB révisé,
répartition uniforme, assurance imposée, `DISP`, nettoyage de la désignation, RFCV annulés…
Ce n'est pas le rôle de l'équipe outils : elle conçoit les outils, l'opérationnel traite les dossiers.

**But :** les collègues de l'opérationnel de Karta préparent eux-mêmes le XML et le corps de leurs
dossiers, au bureau comme à distance, sans faire appel à l'équipe outils.

**Réussite :** un collègue mène un dossier de bout en bout (dépôt du RFCV → réglages → contrôle →
téléchargement → déclaration) sans appeler personne, y compris pour les cas déjà rencontrés
(revalorisation du FOB, Takikro, RFCV éclaté…).

## 2. Objectifs, non-objectifs, anti-objectifs

**Objectifs**
- Déposer un ou plusieurs RFCV (PDF générés ; un dossier par RFCV).
- Régler chaque dossier avec tout ce que l'équipe outils fait aujourd'hui à la main (§5.3).
- Voir un récapitulatif chiffré et des alertes **avant** de télécharger.
- Télécharger le XML ASYCUDA et le corps SYDAM (`corps_<nom>.txt`).
- Régénérer librement un brouillon ; marquer le dossier « Déclaré dans SYDAM » quand il est déposé.
- Gérer les RFCV annulés (libérer leurs châssis) sans ligne de commande.
- Savoir qui a fait quoi (historique par dossier).

**Non-objectifs**
- Toute action dans SYDAM (connexion, saisie, stockage) : c'est le domaine de sydam-cli.
- Ouverture à d'autres sociétés que Karta, inscription libre, facturation, quotas
  (le projet de plateforme de clés `FUTURE_API_KEY_PLATFORM.md` est hors périmètre).
- RFCV scannés (OCR) : seuls les PDF générés sont pris en charge, comme aujourd'hui.
- Application mobile.

**Anti-objectifs (l'outil échoue même s'il « marche »)**
- Un brouillon enregistre des châssis dans le registre : un second essai serait refusé en doublon.
- Une valeur change sans que le collègue le voie (désignation, FOB, assurance) : chaque écart
  par rapport au RFCV doit apparaître dans le récapitulatif.
- Un VIN inventé : les VIN viennent toujours du RFCV (la génération de VIN de l'API reste hors de
  l'interface).
- Un dossier ou un fichier déclaré perdu.

## 3. Contraintes

- **Hébergement :** serveur local de Karta, en Docker. Accès à distance par **Cloudflare Tunnel**
  (`cloudflared`, aucun port entrant ouvert) ; authentification par **Cloudflare Access**
  (liste d'adresses e-mail de l'équipe ; gratuit jusqu'à 50 utilisateurs).
- **Existant Cloudflare (vérifié le 18/11/2026) :** compte Karta avec la zone `karta-transit.ci`
  (et d'autres zones Karta), organisation Zero Trust `groupekarta.cloudflareaccess.com` déjà
  configurée, tunnels déjà en service (dont `pve-karta`, `SVR-KT`, `sydam`). L'application s'y
  branche : un nouveau tunnel (ou une route sur un tunnel existant du serveur choisi), un nom
  d'hôte du type `generation.karta-transit.ci`, une application Access avec la liste de l'équipe.
- **Moteur :** la génération reste celle de pdf-xml-asycuda (Python, `pdfplumber`). Mesure sur un
  RFCV de 300 motos : ~11 s de CPU, ~280 Mo de mémoire. D'où l'hébergement local plutôt que
  serverless (Cloudflare Workers : 128 Mo, `pypdfium2` natif).
- **Profil société :** `profils/karta-transit.ini` (bureau CIAB6, déclarant 00537M, banque BDU1…).
- **API existante :** plus utilisée depuis longtemps (décision du responsable, 18/11/2026). Elle
  reste dans le code mais n'est servie que derrière Cloudflare Access, comme l'application ;
  l'instance Render est arrêtée. Il n'y a donc qu'**un seul registre des châssis** : celui du serveur.
- **Taux douanier :** saisi par dossier (valeur proposée : la dernière utilisée ; aujourd'hui 596,302).
- **Sorties identiques à la CLI :** pour les mêmes réglages, l'application produit exactement le
  même XML et le même corps que `converter.py … --corps` (sortie de référence).
- Langue de l'interface : français.

## 4. Approches envisagées

| | Approche | Bilan |
|---|---|---|
| **A (retenue)** | Interface web ajoutée à pdf-xml-asycuda : pages servies par FastAPI (Jinja2 + htmx), base SQLite locale | Un seul code, réutilise directement le moteur ; interface sobre |
| B | Application séparée (React/Next.js) appelant l'API | Deux projets, deux langages, deux déploiements pour une équipe interne |
| C | Application Go (comme sydam-cli) appelant l'API | Cumule B et la réécriture future du parseur |

Hébergement : Render gratuit (pas de disque persistant, mise en veille), Cloudflare Workers + D1
(limites de CPU/mémoire incompatibles avec le moteur) et Cloudflare Containers (payant) écartés au
profit du **serveur local + Cloudflare Tunnel + Access**, choisi par le responsable.

## 5. Ce qui est décidé

### 5.1 Utilisateurs et accès
- Équipe opérationnelle de Karta ; identité = e-mail fourni par Cloudflare Access.
- L'application **vérifie le jeton Access** (en-tête `Cf-Access-Jwt-Assertion`, signature et
  audience) : pas de mot de passe dans l'application, et refus de toute requête sans jeton valide
  (protection si quelqu'un atteint le serveur sans passer par le tunnel). En développement local,
  un mode explicite permet de simuler un utilisateur.
- Deux rôles : **opérateur** (tout le cycle d'un dossier) et **administrateur** (en plus :
  annulation/restauration de RFCV, retour d'un dossier déclaré en brouillon, réglages par défaut).
  Les administrateurs sont une liste d'e-mails en configuration.

### 5.2 Cycle d'un dossier
```
Brouillon ──(générer, autant de fois que voulu)──> Brouillon
Brouillon ──« Déclaré dans SYDAM »──> Déclaré      (châssis enregistrés dans le registre)
Déclaré ──(admin : remettre en brouillon)──> Brouillon   (châssis retirés du registre)
RFCV annulé (admin) ──> Annulé                      (châssis libérés, cf. registre.py annuler)
```
- **Générer un brouillon n'écrit jamais dans le registre des châssis.** Les châssis déjà
  enregistrés (dossiers déclarés) ou présents dans un autre brouillon apparaissent en **alerte**.
- « Déclaré dans SYDAM » enregistre les châssis ; s'ils sont déjà enregistrés par un autre
  dossier, le passage est **refusé** avec le RFCV d'origine et la marche à suivre (annulation du
  RFCV d'origine par un admin si celui-ci a été annulé).
- Un dossier déclaré est figé : ses fichiers ne sont plus régénérés.
- Le registre utilisé est celui de pdf-xml-asycuda (`chassis_registry`, avec l'historique des
  annulations) ; `registre.py` reste utilisable sur la même base.
- **Sens du registre :** « enregistré » veut désormais dire **déclaré dans SYDAM**. En conséquence,
  la conversion (CLI, API, application) devient par défaut un **contrôle seul**, sans écriture
  dans le registre ; l'écriture se fait au passage « Déclaré dans SYDAM » (ou, en CLI, par une
  option explicite). *Choix de conception.*
- **Départ à zéro** (décision du responsable) : aucun dossier passé n'est importé ; le registre
  démarre vide.

### 5.3 Réglages d'un dossier
Proposés avec des valeurs par défaut, modifiables, tous conservés avec chaque génération :
- profil société (Karta par défaut) ; n° de dossier, manifeste, nationalité du transport,
  rapport de paiement (facultatifs) ;
- **Takikro** (proposé coché si le RFCV est routier venu du Togo) ; **DISP** (case 28) ;
- **taux douanier** ;
- **FOB** : celui du RFCV, ou **FOB révisé** (total) réparti **au prorata** des FOB du RFCV ou
  **uniformément** ;
- **fret** : celui du RFCV ou imposé (total ou par article) ;
- **assurance** : formule (défaut), attestée (case 21), ou **imposée** (total ou par article) ;
- *Choix de conception, unités et saisie :* FOB et fret se saisissent dans la devise du RFCV,
  l'assurance en XOF (comme dans le XML). « Par article » = un même montant pour chaque article
  (multiplié par le nombre d'articles) ; pas de saisie ligne par ligne. Un fret imposé, comme un
  FOB révisé, recalcule l'assurance quand elle est « formule ». Exemple de référence :
  RFCV 6014670 avec FOB 5 400, fret 2 000 et assurance 93 par article → CIF 7 493 par article.
- **désignation** : désignation courte proposée (ex. « TRICYLE-APSONIC- » → `TRICYCLE`,
  « MOTO-APSONIC- » → `MOTO`), modifiable ; appliquée aux marques (case 31) et à la description
  commerciale.

### 5.4 Récapitulatif et alertes (avant téléchargement)
- Totaux : articles, FOB (case 22), fret, assurance, CIF, colis (case 6), poids brut/net, VIN.
- Valeurs par article (distinctes et leur nombre, ex. « 300 × 43 101 »), et les cases clés du corps :
  bureaux, cases 10, 18, 28, 31, 40.
- Écarts par rapport au RFCV (FOB révisé, assurance imposée, désignation modifiée).
- Alertes bloquantes ou non (au choix du builder, voir §6) : châssis déjà déclarés ou dans un
  autre brouillon ; colis à 0 ; somme des articles ≠ total ; FOB attestés différents entre
  articles (cas 6014629) ; désignation non nettoyée ; code SH inhabituel pour la désignation
  (ex. tricycle en 8704 au lieu de 8711).
- *Choix de conception, code SH inhabituel :* pas de table écrite à la main. Est signalé un code
  SH jamais vu pour cette désignation courte dans les dossiers **déclarés** ; un administrateur
  peut marquer la paire (désignation, code) comme normale. Au démarrage (registre vide), l'alerte
  ne se déclenche pas tant qu'aucun dossier n'est déclaré.

### 5.5 Écrans
1. **Dossiers** : liste (RFCV, date, auteur, statut, articles, FOB), recherche par n° RFCV ou VIN.
2. **Nouveau** : dépôt d'un ou plusieurs PDF ; chaque PDF devient un dossier en brouillon.
3. **Dossier** : réglages, bouton Générer, récapitulatif et alertes, téléchargements (XML, corps,
   PDF d'origine), historique des générations, bouton « Déclaré dans SYDAM ».
4. **Châssis** (admin) : recherche d'un VIN, RFCV annulés, annulation/restauration avec motif.

### 5.6 Stockage
- SQLite sur un volume du serveur : utilisateurs vus, dossiers, réglages, générations, journal.
- Fichiers (PDF, XML, corps de chaque génération) sur le même volume, jamais écrasés.
- Le registre des châssis reste `data/chassis_registry.db`, sur ce volume.
- Sauvegarde quotidienne du volume (méthode au choix du builder, voir §6).

### 5.7 Évolutions du moteur (pdf-xml-asycuda)
Rendre disponibles comme fonctions testées (CLI et API comprises) ce qui est fait à la main :
répartition uniforme du FOB, assurance et fret imposés, désignation imposée, génération
« brouillon » sans écriture dans le registre (contrôle des doublons en lecture seule, rendu sous
forme d'alertes), et un résumé structuré d'une génération (totaux, valeurs distinctes, écarts,
alertes) utilisé par le récapitulatif.

## 6. Laissé au builder
- Structure du code (paquet `src/webapp/` ou équivalent), ORM ou `sqlite3`, gabarits, style.
- Détail des tables et des migrations.
- Quelles alertes bloquent la déclaration et lesquelles sont de simples avertissements, à
  condition que les doublons de châssis bloquent toujours la déclaration.
- Mise en page exacte des écrans, pagination, recherche.
- Méthode de sauvegarde et rétention.
- Fichiers de déploiement (Dockerfile/compose, configuration `cloudflared`), documentation
  d'installation pour le serveur. *Choix proposé, à confirmer à l'installation :* une VM ou un
  conteneur LXC dédié sur le serveur Proxmox (`pve-karta`), avec Docker, et son propre tunnel.
