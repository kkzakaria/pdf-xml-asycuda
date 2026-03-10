# Design — Registre de châssis RFCV

**Date** : 2026-03-10
**Statut** : Approuvé

## Objectif

Sauvegarder les numéros de châssis issus du traitement RFCV (extraits des PDFs et générés automatiquement) afin d'avertir l'utilisateur quand un châssis a déjà été traité par le système.

## Périmètre

- Deux registres séparés : châssis extraits des PDFs RFCV + VINs générés automatiquement
- Blocage du traitement en cas de doublon (erreur HTTP 409)
- Paramètre `force_reprocess=true` pour forcer le retraitement
- Endpoints d'administration du registre

## Composant principal : `ChassisRegistry`

**Fichier** : `src/chassis_registry.py`
**Stockage** : SQLite à `data/chassis_registry.db`

### Tables

**`extracted_chassis`** — châssis lus dans les PDFs RFCV :

| Colonne | Type | Description |
|---|---|---|
| `chassis_number` | TEXT PRIMARY KEY | Numéro de châssis brut |
| `registered_at` | TEXT | Date ISO 8601 du premier traitement |
| `filename` | TEXT | Nom du PDF source |
| `rfcv_number` | TEXT | Numéro RFCV (ex: CI-2025-18236) |

**`generated_chassis`** — VINs générés automatiquement :

| Colonne | Type | Description |
|---|---|---|
| `chassis_number` | TEXT PRIMARY KEY | VIN généré (17 chars ISO 3779) |
| `registered_at` | TEXT | Date ISO 8601 de génération |
| `filename` | TEXT | Nom du PDF source |
| `rfcv_number` | TEXT | Numéro RFCV source |

### Interface publique

```python
class DuplicateChassisError(Exception):
    chassis_number: str
    first_seen_date: str
    first_filename: str
    first_rfcv_number: str

class ChassisRegistry:
    def check_extracted(chassis_number: str) -> Optional[dict]
    def register_extracted(chassis_number: str, filename: str, rfcv_number: str)
    def check_generated(chassis_number: str) -> Optional[dict]
    def register_generated(chassis_number: str, filename: str, rfcv_number: str)
```

Thread-safe via `threading.Lock`, même pattern que `ChassisSequenceManager`.

## Flux de traitement

### Châssis extraits (mode normal)

1. `rfcv_parser._extract_chassis_number()` détecte le numéro dans la description
2. `registry.check_extracted(chassis_number)` — vérifie le registre
3. Si doublon ET `force_reprocess=False` → lève `DuplicateChassisError`
4. Si pas de doublon OU `force_reprocess=True` → `registry.register_extracted(...)` puis continue

**Comportement multi-doublons** : tous les châssis en doublon du même RFCV sont collectés avant de bloquer — l'utilisateur voit la liste complète en une seule erreur.

### VINs générés (mode `generate_chassis=true`)

1. VIN généré normalement via `ChassisSequenceManager` (unicité garantie par séquence)
2. Après génération → `registry.register_generated(...)` (traçabilité uniquement, pas de vérification de doublon)

## Propagation du paramètre `force_reprocess`

Ajout de `force_reprocess: bool = False` dans le dataclass `ChassisConfig` (`src/models.py`). Le parser reçoit déjà `chassis_config`, aucun changement de signature requis.

## Couche API

### Requête

Nouveau champ disponible sur tous les endpoints de conversion :

```
force_reprocess=true   # form field (bool, défaut: false)
```

### Réponse en cas de doublon — HTTP 409 Conflict

```json
{
  "success": false,
  "error": "duplicate_chassis",
  "detail": "Le châssis LZSHCKZS2S8000001 a déjà été traité",
  "duplicates": [
    {
      "chassis_number": "LZSHCKZS2S8000001",
      "first_seen_date": "2025-11-14T10:23:00",
      "first_filename": "DOSSIER_18236.pdf",
      "first_rfcv_number": "CI-2025-18236"
    }
  ],
  "hint": "Relancer avec force_reprocess=true pour forcer le retraitement"
}
```

### Endpoints d'administration

Ajoutés dans `src/api/routes/chassis.py` :

| Endpoint | Méthode | Description |
|---|---|---|
| `/api/v1/chassis/registry/extracted` | GET | Liste tous les châssis extraits |
| `/api/v1/chassis/registry/generated` | GET | Liste tous les VINs générés |
| `/api/v1/chassis/registry/{chassis_number}` | GET | Détail d'un châssis |
| `/api/v1/chassis/registry/{chassis_number}` | DELETE | Supprimer une entrée (admin) |

## Fichiers modifiés

| Fichier | Nature |
|---|---|
| `src/chassis_registry.py` | **Nouveau** — `ChassisRegistry` + `DuplicateChassisError` |
| `src/models.py` | Ajout `force_reprocess: bool = False` dans `ChassisConfig` |
| `src/rfcv_parser.py` | Injecter `ChassisRegistry`, vérifier avant assigner, enregistrer après |
| `src/chassis_generator.py` | Enregistrer chaque VIN généré dans `generated_chassis` |
| `src/api/models/api_models.py` | Ajout `force_reprocess` dans les modèles de requête |
| `src/api/routes/convert.py` | Catch `DuplicateChassisError` → HTTP 409 |
| `src/api/routes/chassis.py` | Nouveaux endpoints d'administration du registre |

## Tests

| Fichier | Contenu |
|---|---|
| `tests/test_chassis_registry.py` | Tests unitaires : insert, détection doublon, bypass `force_reprocess` |
| `tests/api/test_convert_duplicate.py` | Tests intégration : 409 sur doublon, 200 avec `force_reprocess=true` |
