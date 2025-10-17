# Guide d'Utilisation de Swagger UI

Guide complet pour tester l'API PDF-XML-ASYCUDA avec Swagger UI (interface `/docs`).

## 🎯 Accès à la Documentation Interactive

### En Local
```
http://localhost:8000/docs
```

### Sur Render (Production)
```
https://votre-service.onrender.com/docs
```

---

## 🔐 Authentification dans Swagger UI

L'API nécessite une clé API pour tous les endpoints protégés. Swagger UI permet d'entrer cette clé une seule fois pour tous les tests.

### Étape 1: Obtenir une Clé API

**Si vous êtes administrateur** (première fois):

```bash
# Générer une nouvelle clé
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

**Si vous avez déjà une clé**:
- Utilisez la clé que l'administrateur vous a fournie
- Ou la clé que vous avez configurée dans `.env` (local) ou Render Dashboard (production)

### Étape 2: S'Authentifier dans Swagger UI

1. **Ouvrir Swagger UI**:
   - Aller sur http://localhost:8000/docs

2. **Cliquer sur le bouton "Authorize"** (en haut à droite):
   - Icône: 🔓 (cadenas ouvert)
   - Texte: "Authorize"

3. **Entrer la clé API**:
   - Dans le champ **"Value"** sous **"APIKeyHeader (apiKey)"**
   - Coller votre clé API
   - Exemple: `xK7_9mPqR2tYvN8zLw3jH4cF6dB1sA5gT0uV-eI9wX2yQ`

4. **Cliquer sur "Authorize"** (bouton bleu)

5. **Fermer la popup**:
   - Cliquer sur "Close"
   - Le cadenas devient 🔒 (fermé) = vous êtes authentifié

✅ **C'est tout !** Tous les endpoints peuvent maintenant être testés avec cette clé.

---

## 📋 Tester les Endpoints

### 1. Health Check (Public, pas d'auth requise)

**Endpoint**: `GET /api/v1/health`

1. Cliquer sur **"GET /api/v1/health"**
2. Cliquer sur **"Try it out"**
3. Cliquer sur **"Execute"**

**Résultat attendu**:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2025-10-17T13:45:00Z"
}
```

### 2. Conversion Synchrone (Authentification requise)

**Endpoint**: `POST /api/v1/convert`

1. **S'assurer d'être authentifié** (cadenas 🔒 fermé)

2. Cliquer sur **"POST /api/v1/convert"**

3. Cliquer sur **"Try it out"**

4. **Upload un fichier PDF**:
   - Cliquer sur **"Choose File"** (ou **"Browse"**)
   - Sélectionner un fichier PDF RFCV de test

5. Cliquer sur **"Execute"**

**Résultat attendu** (succès):
```json
{
  "success": true,
  "job_id": "conv_xYz123AbC456",
  "filename": "test.pdf",
  "output_file": "test.xml",
  "message": "Conversion réussie",
  "metrics": {
    "items_count": 26,
    "fill_rate": 69.0,
    "xml_valid": true
  },
  "processing_time": 1.23
}
```

**Résultat attendu** (sans authentification):
```json
{
  "detail": "API key manquante. Fournir X-API-Key header."
}
```

### 3. Conversion Asynchrone

**Endpoint**: `POST /api/v1/convert/async`

1. S'authentifier (si pas déjà fait)
2. Cliquer sur **"Try it out"**
3. Upload un fichier PDF
4. Cliquer sur **"Execute"**

**Résultat**:
```json
{
  "job_id": "conv_AbC789XyZ",
  "status": "pending",
  "message": "Conversion en cours",
  "created_at": "2025-10-17T13:45:30Z"
}
```

**Ensuite**, utiliser le `job_id` pour vérifier le statut:

### 4. Vérifier le Statut d'un Job

**Endpoint**: `GET /api/v1/convert/{job_id}`

1. Cliquer sur **"Try it out"**
2. Entrer le `job_id` reçu précédemment
3. Cliquer sur **"Execute"**

**Résultat**:
```json
{
  "job_id": "conv_AbC789XyZ",
  "status": "completed",
  "filename": "test.pdf",
  "created_at": "2025-10-17T13:45:30Z",
  "completed_at": "2025-10-17T13:45:31Z",
  "progress": 100,
  "message": "Conversion terminée",
  "error": null
}
```

### 5. Télécharger le XML Généré

**Endpoint**: `GET /api/v1/convert/{job_id}/download`

1. Cliquer sur **"Try it out"**
2. Entrer le `job_id`
3. Cliquer sur **"Execute"**
4. **Cliquer sur "Download file"** pour télécharger le XML

---

## 🎨 Interface Swagger UI

### Codes de Couleur

- 🟢 **Vert (200)**: Succès
- 🟡 **Jaune (400-499)**: Erreur client
  - 401: Non authentifié (clé API manquante/invalide)
  - 404: Ressource introuvable
  - 422: Validation échouée
  - 429: Rate limit dépassé
- 🔴 **Rouge (500-599)**: Erreur serveur

### Symboles d'Authentification

- 🔓 **Cadenas ouvert**: Non authentifié
- 🔒 **Cadenas fermé**: Authentifié avec clé API

---

## 📊 Exemples de Scénarios

### Scénario 1: Conversion Simple

```
1. Cliquer "Authorize" → Entrer clé API → Authorize → Close
2. POST /api/v1/convert → Try it out → Upload PDF → Execute
3. Vérifier résultat (success: true, job_id: ...)
4. GET /api/v1/convert/{job_id}/download → Télécharger XML
```

### Scénario 2: Batch Processing

```
1. S'authentifier
2. POST /api/v1/batch → Try it out
3. Upload PLUSIEURS fichiers PDF (Ctrl+Click pour sélection multiple)
4. Configurer workers (ex: 4)
5. Execute → Noter le batch_id
6. GET /api/v1/batch/{batch_id}/status → Vérifier progression
7. GET /api/v1/batch/{batch_id}/results → Voir tous les résultats
```

### Scénario 3: Téléchargement Direct par File ID

```
1. S'authentifier
2. Supposons que vous avez déjà un file_id: "output_20251017.xml"
3. GET /api/v1/files/{file_id}/xml → Try it out
4. Entrer: output_20251017.xml
5. Execute → Download file
```

---

## ⚠️ Problèmes Courants

### "API key manquante"

**Cause**: Pas authentifié ou clé expirée

**Solution**:
1. Vérifier le cadenas: doit être 🔒 (fermé)
2. Cliquer "Authorize" et re-entrer la clé
3. Rafraîchir la page si nécessaire

### "API key invalide"

**Cause**: Clé incorrecte

**Solution**:
1. Vérifier qu'il n'y a pas d'espaces avant/après la clé
2. Demander une nouvelle clé à l'administrateur
3. En local: vérifier `.env` → `API_KEYS`

### "Rate limit exceeded" (429)

**Cause**: Trop de requêtes en peu de temps

**Limites par défaut**:
- Uploads individuels: 10/minute
- Uploads async: 20/minute
- Batch: 5/heure

**Solution**:
- Attendre quelques minutes
- En local: désactiver rate limiting dans `.env`: `API_RATE_LIMIT_ENABLED=False`

### Upload échoue avec fichier volumineux

**Cause**: Fichier > 50MB

**Solution**:
- Compresser le PDF
- Ou augmenter `API_MAX_UPLOAD_SIZE` dans la configuration

---

## 🔍 Inspection des Requêtes

### Voir le cURL Généré

Swagger UI génère automatiquement la commande cURL équivalente:

1. Exécuter une requête
2. Scroller vers le bas dans la réponse
3. Chercher **"Curl"** (onglet)
4. Copier la commande

**Exemple**:
```bash
curl -X 'POST' \
  'http://localhost:8000/api/v1/convert' \
  -H 'accept: application/json' \
  -H 'X-API-Key: votre_cle_api' \
  -H 'Content-Type: multipart/form-data' \
  -F 'file=@test.pdf'
```

Vous pouvez utiliser cette commande directement dans votre terminal !

---

## 🎓 Conseils d'Utilisation

### 1. Persistence de l'Authentification

La clé API est **sauvegardée localement** dans votre navigateur:
- Pas besoin de re-s'authentifier à chaque rechargement
- Fonctionne tant que vous ne videz pas le cache

### 2. Tester Plusieurs Scénarios

Swagger UI garde l'historique des requêtes:
- Les valeurs précédentes sont pré-remplies
- Pratique pour re-tester rapidement

### 3. Validation Automatique

Swagger UI valide les paramètres AVANT l'envoi:
- Champs obligatoires
- Formats de données
- Tailles de fichiers

### 4. Documentation Intégrée

Chaque endpoint a:
- **Description**: Ce qu'il fait
- **Parameters**: Quels paramètres acceptés
- **Responses**: Exemples de réponses

Cliquer sur "Schema" pour voir la structure complète.

---

## 📱 Alternatives à Swagger UI

Si Swagger UI ne fonctionne pas ou si vous préférez autre chose:

### ReDoc (Même serveur)
```
http://localhost:8000/redoc
```

- Plus belle documentation
- Pas de tests interactifs (lecture seule)

### Postman
1. Importer OpenAPI spec: http://localhost:8000/openapi.json
2. Configurer header `X-API-Key` dans Collection
3. Tester tous les endpoints

### cURL (Terminal)
Voir les exemples dans `RENDER_DEPLOYMENT.md`

### HTTPie (Terminal, plus user-friendly)
```bash
http POST localhost:8000/api/v1/convert \
  X-API-Key:votre_cle \
  file@test.pdf
```

---

## 🔗 Ressources Complémentaires

- **API Reference**: `/redoc` (documentation alternative)
- **OpenAPI Spec**: `/openapi.json` (schéma JSON)
- **Health Check**: `/api/v1/health` (vérifier disponibilité)
- **Root Endpoint**: `/` (liste tous les endpoints)

---

## 🎯 Checklist Tests Complets

Pour tester toute l'API via Swagger UI:

- [ ] **Authentification**: Authorize avec clé API valide
- [ ] **Health Check**: GET /api/v1/health (public)
- [ ] **Conversion Sync**: POST /api/v1/convert avec PDF
- [ ] **Conversion Async**: POST /api/v1/convert/async
- [ ] **Job Status**: GET /api/v1/convert/{job_id}
- [ ] **Job Result**: GET /api/v1/convert/{job_id}/result
- [ ] **Download XML**: GET /api/v1/convert/{job_id}/download
- [ ] **Batch Upload**: POST /api/v1/batch (multi-files)
- [ ] **Batch Status**: GET /api/v1/batch/{batch_id}/status
- [ ] **Batch Results**: GET /api/v1/batch/{batch_id}/results
- [ ] **File Download**: GET /api/v1/files/{file_id}/xml
- [ ] **Metrics**: GET /api/v1/metrics
- [ ] **Test sans auth**: Vérifier 401 (logout puis retry)
- [ ] **Test rate limit**: Faire >10 uploads/minute

---

**Dernière mise à jour**: 2025-10-17
**Version API**: 1.1.0 (avec authentification)

**Besoin d'aide ?** Consultez `RENDER_DEPLOYMENT.md` pour la configuration ou ouvrez une issue sur GitHub.
