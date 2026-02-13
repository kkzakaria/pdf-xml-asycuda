## Revue de la PR #52 — Logging des requêtes API et statistiques d'utilisation persistantes

### Résumé

Cette PR ajoute deux fonctionnalités transversales :
1. Un middleware de logging HTTP (`RequestLoggingMiddleware`)
2. Un service de statistiques d'utilisation persistantes (`UsageStatsService`) avec 3 endpoints dédiés

Le remplacement des `print()` par des appels `logger` dans `background.py` et `conversion_service.py` est un nettoyage bienvenu.

---

### Points positifs

- **Bonne couverture de tests** — 19 tests couvrant l'initialisation, la persistance, la récupération de fichier corrompu, et les différents compteurs.
- **Thread-safety** — Utilisation cohérente de `threading.Lock` dans `UsageStatsService`, pattern déjà validé par `ChassisSequenceManager`.
- **Remplacement des `print()` par `logger`** — Cohérent avec la PR #51 (logging centralisé). Bonne continuité.
- **Configuration flexible** — `stats_enabled` / `stats_file` dans `config.py` avec préfixe `API_`, et `.env.example` documenté.
- **Exclusion du health check** — `SKIP_PATHS` dans le middleware évite du bruit inutile.
- **`.gitignore` mis à jour** — Le fichier `data/usage_stats.json` ne sera pas commité.

---

### Problèmes à corriger

#### 1. **CRITIQUE — Sauvegarde disque à chaque requête HTTP** (`usage_stats_service.py`)

Chaque appel à `track_request()` fait un `_save()` qui écrit le fichier JSON complet sur disque. Le middleware appelle `track_request()` **pour chaque requête** (sauf `/health`). En production sous charge, cela signifie :
- I/O disque bloquant à chaque requête dans un contexte async (via `await call_next` puis code sync)
- Contention sur le lock si des requêtes concurrentes arrivent
- Usure disque inutile

**Suggestion** : Implémenter un flush périodique (ex: toutes les N secondes ou tous les N appels) plutôt qu'une sauvegarde à chaque requête. Ou utiliser un `asyncio.Queue` + tâche background pour batch les écritures.

```python
# Exemple d'approche avec flush périodique
def _save_if_needed(self) -> None:
    self._dirty = True
    now = time.time()
    if now - self._last_save > self.FLUSH_INTERVAL:
        self._save()
        self._last_save = now
```

#### 2. **BUG — Endpoints stats dans le mauvais routeur** (`health.py:152-199`)

Les 3 endpoints `/api/v1/stats`, `/api/v1/stats/conversions`, `/api/v1/stats/requests` sont ajoutés dans `health.py` qui a le préfixe `tags=["Health"]`. Problèmes :
- Dans Swagger, ils apparaîtront sous la section "Health" au lieu d'avoir leur propre section
- Le routeur `health.py` n'a **pas** de préfixe de path, donc ça fonctionne, mais c'est incohérent avec l'architecture `routes/` où chaque fichier a une responsabilité claire
- Les endpoints ne sont pas listés dans la route racine (`main.py` root endpoint `endpoints` dict)

**Suggestion** : Créer un `src/api/routes/stats.py` dédié avec `tags=["Statistics"]`, et l'inclure dans `main.py`. Mettre à jour la route racine.

#### 3. **BUG — `except Exception: pass` silencieux** (`request_logging.py:54-57`)

```python
try:
    from ..core.config import settings
    if settings.stats_enabled:
        from ..services.usage_stats_service import usage_stats
        usage_stats.track_request(method, status_code)
except Exception:
    pass
```

Un `except Exception: pass` avale silencieusement toutes les erreurs, y compris les bugs de programmation (TypeError, KeyError, etc.). Si `track_request` casse un jour, vous ne le saurez jamais.

**Suggestion** : Logger au minimum au niveau `debug` ou `warning` :
```python
except Exception as e:
    logger.debug("Stats tracking skipped: %s", e)
```

#### 4. **Import au top-level dans `main.py`** (lignes 130-131)

```python
# Middleware de logging des requêtes
from .core.request_logging import RequestLoggingMiddleware
app.add_middleware(RequestLoggingMiddleware)
```

L'import est fait au milieu du fichier, entre le middleware CORS et les exception handlers. Tous les autres imports sont au sommet du fichier.

**Suggestion** : Déplacer `from .core.request_logging import RequestLoggingMiddleware` avec les autres imports en haut du fichier.

#### 5. **Singleton créé à l'import** (`usage_stats_service.py:180-185`)

```python
def _create_usage_stats() -> UsageStatsService:
    try:
        from ..core.config import settings
        return UsageStatsService(settings.stats_file)
    except Exception:
        return UsageStatsService()

usage_stats = _create_usage_stats()
```

Le singleton est créé dès l'import du module. Si `settings` n'est pas encore configuré (ex: pendant les tests, ou si un import circulaire survient), il fallback silencieusement avec le chemin par défaut. Ça peut créer des fichiers `data/usage_stats.json` inattendus pendant les tests.

**Suggestion** : Utiliser un pattern lazy singleton ou initialiser explicitement dans le `lifespan` de FastAPI :
```python
_usage_stats: Optional[UsageStatsService] = None

def get_usage_stats() -> UsageStatsService:
    global _usage_stats
    if _usage_stats is None:
        _usage_stats = UsageStatsService(settings.stats_file)
    return _usage_stats
```

#### 6. **Tests d'intégration — fixture `client` non importée** (`test_usage_stats.py:216-247`)

La classe `TestStatsEndpoints` utilise la fixture `client` de `conftest.py`, mais le fichier importe uniquement `UsageStatsService`. La fixture sera trouvée automatiquement par pytest via conftest — ça devrait fonctionner. Cependant :
- Les tests d'intégration ne vérifient **pas** que l'authentification est requise (pas de test sans API key → 401)
- Il n'y a pas de test pour vérifier que `stats_enabled=False` désactive bien le tracking

---

### Suggestions d'amélioration (non bloquantes)

#### A. Compteurs `successful`/`failed` dans `track_batch` ne tiennent pas compte des résultats partiels

```python
if failed == 0:
    self._stats["batches"]["successful"] += 1
else:
    self._stats["batches"]["failed"] += 1
```

Un batch avec 99 succès et 1 échec est compté comme "failed". Ajouter `batches.partial` ou `batches.total_successful_files` / `batches.total_failed_files` serait plus informatif.

#### B. Pas de mécanisme de rotation/reset des stats

Les compteurs ne font que croître. Il serait utile d'avoir :
- Un endpoint `DELETE /api/v1/stats` (ou `POST /api/v1/stats/reset`) pour remettre à zéro
- Ou des stats par période (daily/weekly)

#### C. `request.client` peut être `None`

Dans `request_logging.py:38` :
```python
client_ip = request.client.host if request.client else "unknown"
```

C'est bien géré ici, mais dans `main.py:149` et `main.py:169`, le même pattern est utilisé avec f-strings. Cohérent.

#### D. Duplication du code de tracking dans `convert.py`

Le pattern `usage_stats.track_conversion(...)` est répété ~10 fois dans `convert.py` avec des variations mineures (`has_chassis`, `has_payment`). Un helper interne au module réduirait la duplication :

```python
def _track(success: bool, is_async: bool = False, **kwargs):
    usage_stats.track_conversion(success=success, is_async=is_async, **kwargs)
```

#### E. `import pytest_asyncio` non utilisé dans les tests

`test_usage_stats.py:4` importe `pytest_asyncio` et `tempfile` mais ne les utilise pas directement (les fixtures n'utilisent pas `@pytest_asyncio.fixture`).

---

### Verdict

La fonctionnalité est utile et bien testée au niveau unitaire. Cependant, **le problème de performance I/O (point 1)** est un risque réel en production et devrait être adressé avant merge. Les points 2 à 5 sont des corrections d'architecture/propreté qui amélioreraient la maintenabilité.

**Recommandation : Changements demandés** — adresser au minimum les points 1 (flush périodique) et 3 (logging des erreurs silencieuses) avant merge.
