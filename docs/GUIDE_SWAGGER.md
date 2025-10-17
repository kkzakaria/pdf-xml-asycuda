# Guide d'Utilisation Swagger UI

Guide pratique pour tester votre API via l'interface Swagger UI.

## 🌐 Accéder à la Documentation

**URL de votre API:** https://pdf-xml-asycuda-api.onrender.com/docs

## 📋 Interface Swagger UI

### Vue d'Ensemble

Quand vous ouvrez `/docs`, vous verrez:

```
┌─────────────────────────────────────────────────────┐
│  API Convertisseur PDF RFCV → XML ASYCUDA          │
│  Version 1.0.0                                      │
├─────────────────────────────────────────────────────┤
│  🟢 Health                                          │
│    GET  /api/v1/health                             │
│    GET  /api/v1/metrics                            │
│    GET  /api/v1/metrics/{job_id}                   │
│                                                     │
│  📄 Convert                                         │
│    POST /api/v1/convert                            │
│    POST /api/v1/convert/async                      │
│    GET  /api/v1/convert/{job_id}                   │
│    GET  /api/v1/convert/{job_id}/result            │
│    GET  /api/v1/convert/{job_id}/download          │
│                                                     │
│  📦 Batch                                           │
│    POST /api/v1/batch                              │
│    GET  /api/v1/batch/{batch_id}/status            │
│    GET  /api/v1/batch/{batch_id}/results           │
│    GET  /api/v1/batch/{batch_id}/report            │
│                                                     │
│  📁 Files                                           │
│    GET  /api/v1/files/{file_id}/xml                │
│    GET  /api/v1/files/{file_id}/metadata           │
└─────────────────────────────────────────────────────┘
```

## 🧪 Test 1: Health Check (Simple)

### Étape 1: Trouver l'Endpoint

1. **Scrollez** jusqu'à la section **"Health"** (verte)
2. **Cliquez** sur `GET /api/v1/health`
3. L'endpoint **s'ouvre** et affiche les détails

### Étape 2: Tester l'Endpoint

```
┌─────────────────────────────────────────────────────┐
│  GET /api/v1/health                                 │
│  Health check                                       │
│                                                     │
│  Vérifie l'état de santé de l'API                  │
│                                                     │
│  [ Try it out ]                                    │
└─────────────────────────────────────────────────────┘
```

1. **Cliquez** sur le bouton **"Try it out"** (en haut à droite)
2. Le bouton devient **"Execute"**
3. **Cliquez** sur **"Execute"**

### Étape 3: Voir la Réponse

Après quelques secondes, vous verrez:

```
┌─────────────────────────────────────────────────────┐
│  Responses                                          │
│                                                     │
│  Code: 200 ✅                                       │
│  Details: Successful Response                       │
│                                                     │
│  Response body:                                     │
│  {                                                  │
│    "status": "healthy",                            │
│    "version": "1.0.0",                             │
│    "uptime_seconds": 61369.95,                     │
│    "total_jobs": 0                                 │
│  }                                                  │
│                                                     │
│  Response headers:                                  │
│  content-type: application/json                    │
│  date: Fri, 17 Oct 2025 07:51:46 GMT              │
└─────────────────────────────────────────────────────┘
```

**Interprétation:**
- ✅ **Code 200**: Succès
- ✅ **status: healthy**: API fonctionne
- ✅ **uptime_seconds**: Temps depuis le dernier redémarrage
- ✅ **total_jobs**: Nombre de conversions effectuées

### Étape 4: Copier la Commande curl

Scrollez jusqu'à voir:

```
┌─────────────────────────────────────────────────────┐
│  Curl                                               │
│                                                     │
│  curl -X 'GET' \                                   │
│    'https://pdf-xml-asycuda-api.onrender.com/...  │
│    -H 'accept: application/json'                   │
│                                                     │
│  [ Copy ]                                          │
└─────────────────────────────────────────────────────┘
```

**Cliquez** sur **"Copy"** pour copier la commande curl complète!

## 🚀 Test 2: Conversion PDF (Avec Upload)

### Étape 1: Préparer un PDF

Avant de commencer, assurez-vous d'avoir un PDF RFCV prêt sur votre ordinateur.

### Étape 2: Ouvrir l'Endpoint de Conversion

1. **Scrollez** jusqu'à la section **"Convert"**
2. **Cliquez** sur `POST /api/v1/convert`
3. **Lisez** la description:
   ```
   Conversion synchrone PDF → XML ASYCUDA
   Upload un fichier PDF et retourne le XML généré immédiatement
   ```

### Étape 3: Try it out

1. **Cliquez** sur **"Try it out"**
2. Vous verrez un formulaire d'upload:

```
┌─────────────────────────────────────────────────────┐
│  POST /api/v1/convert                               │
│                                                     │
│  Request body                                       │
│  ┌───────────────────────────────────────────────┐ │
│  │ file * (required)                             │ │
│  │ [Choose File]  No file chosen                 │ │
│  │                                               │ │
│  │ string($binary)                               │ │
│  └───────────────────────────────────────────────┘ │
│                                                     │
│  [ Execute ]                                       │
└─────────────────────────────────────────────────────┘
```

### Étape 4: Upload le PDF

1. **Cliquez** sur **"Choose File"**
2. **Sélectionnez** votre PDF RFCV
3. Le nom du fichier apparaît: `DOSSIER_18236.pdf`
4. **Cliquez** sur **"Execute"**

### Étape 5: Attendre la Conversion

Vous verrez un indicateur de chargement:
```
⏳ Loading...
```

**Temps de conversion:** ~1-3 secondes pour un PDF standard

### Étape 6: Voir le Résultat

```
┌─────────────────────────────────────────────────────┐
│  Responses                                          │
│                                                     │
│  Code: 200 ✅                                       │
│  Details: Successful Response                       │
│                                                     │
│  Response body:                                     │
│  {                                                  │
│    "success": true,                                │
│    "message": "Conversion réussie",                │
│    "filename": "DOSSIER_18236.pdf",                │
│    "output_file": "output/DOSSIER_18236.xml",     │
│    "xml_content": "<?xml version='1.0'?>...",     │
│    "metrics": {                                    │
│      "total_time": 0.85,                          │
│      "items_count": 5,                            │
│      "containers_count": 2,                       │
│      "fields_filled_rate": 68.5,                  │
│      "xml_valid": true,                           │
│      "warnings": []                               │
│    }                                               │
│  }                                                  │
└─────────────────────────────────────────────────────┘
```

**Interprétation:**
- ✅ **success: true**: Conversion réussie
- 📄 **filename**: Nom du PDF uploadé
- 📄 **output_file**: Chemin du XML généré
- 📄 **xml_content**: Contenu XML complet (scrollable)
- 📊 **metrics**: Statistiques de qualité

### Étape 7: Copier le XML

Le XML complet est dans `xml_content`. Vous pouvez:

1. **Cliquer** sur le texte XML
2. **Sélectionner tout** (Ctrl+A / Cmd+A)
3. **Copier** (Ctrl+C / Cmd+C)
4. **Coller** dans un fichier .xml

Ou scrollez vers le bas et copiez la commande curl pour réutiliser:

```bash
curl -X 'POST' \
  'https://pdf-xml-asycuda-api.onrender.com/api/v1/convert' \
  -H 'accept: application/json' \
  -H 'Content-Type: multipart/form-data' \
  -F 'file=@DOSSIER_18236.pdf;type=application/pdf'
```

## 🔄 Test 3: Conversion Asynchrone (Job Tracking)

### Étape 1: Lancer une Conversion Async

1. **Cliquez** sur `POST /api/v1/convert/async`
2. **Try it out**
3. **Upload** un PDF
4. **Execute**

### Étape 2: Récupérer le Job ID

Réponse:
```json
{
  "job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "processing",
  "message": "Conversion en cours"
}
```

**Copiez** le `job_id` → `a1b2c3d4-e5f6-7890-abcd-ef1234567890`

### Étape 3: Vérifier le Status

1. **Cliquez** sur `GET /api/v1/convert/{job_id}`
2. **Try it out**
3. **Collez** le job_id dans le champ:
   ```
   ┌───────────────────────────────────────────────┐
   │ job_id * (required)                           │
   │ a1b2c3d4-e5f6-7890-abcd-ef1234567890         │
   └───────────────────────────────────────────────┘
   ```
4. **Execute**

Réponse:
```json
{
  "job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "completed",
  "filename": "DOSSIER_18236.pdf",
  "created_at": "2025-10-17T08:00:00Z",
  "completed_at": "2025-10-17T08:00:02Z"
}
```

### Étape 4: Télécharger le XML

1. **Cliquez** sur `GET /api/v1/convert/{job_id}/download`
2. **Try it out**
3. **Collez** le même job_id
4. **Execute**

Le XML sera téléchargé automatiquement! 📥

## 📦 Test 4: Batch Conversion (Plusieurs PDFs)

### Étape 1: Préparer Plusieurs PDFs

Assurez-vous d'avoir 2-3 PDFs disponibles.

### Étape 2: Ouvrir Batch Endpoint

1. **Cliquez** sur `POST /api/v1/batch`
2. **Try it out**

### Étape 3: Upload Multiple Files

```
┌─────────────────────────────────────────────────────┐
│  Request body                                       │
│  ┌───────────────────────────────────────────────┐ │
│  │ files * (required)                            │ │
│  │ [Choose Files]  No files chosen               │ │
│  │                                               │ │
│  │ Array of files                                │ │
│  └───────────────────────────────────────────────┘ │
│                                                     │
│  workers (optional)                                 │
│  ┌───────────────────────────────────────────────┐ │
│  │ 4                                             │ │
│  └───────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

1. **Cliquez** "Choose Files"
2. **Sélectionnez** plusieurs PDFs (Ctrl/Cmd + clic)
3. **Configurez** workers: `4` (parallèle)
4. **Execute**

### Étape 4: Récupérer le Batch ID

Réponse:
```json
{
  "batch_id": "batch_xyz123",
  "total_files": 3,
  "status": "processing"
}
```

### Étape 5: Suivre la Progression

1. **Cliquez** sur `GET /api/v1/batch/{batch_id}/status`
2. **Collez** le batch_id
3. **Execute** (cliquez plusieurs fois pour voir la progression)

Réponse:
```json
{
  "batch_id": "batch_xyz123",
  "status": "processing",
  "total_files": 3,
  "processed": 2,
  "successful": 2,
  "failed": 0,
  "progress_percentage": 66.67
}
```

### Étape 6: Récupérer le Rapport

Une fois `status: "completed"`:

1. **Cliquez** sur `GET /api/v1/batch/{batch_id}/report`
2. **Collez** le batch_id
3. **Execute**

Vous obtiendrez un rapport détaillé de tous les fichiers!

## 📊 Test 5: Métriques Système

### Voir les Stats Globales

1. **Cliquez** sur `GET /api/v1/metrics`
2. **Try it out**
3. **Execute**

Réponse:
```json
{
  "total_conversions": 42,
  "successful": 40,
  "failed": 2,
  "success_rate": 95.24,
  "avg_processing_time": 1.23,
  "avg_fill_rate": 68.5,
  "total_items": 210,
  "total_containers": 84
}
```

**Statistiques utiles:**
- Nombre total de conversions
- Taux de succès
- Temps de traitement moyen
- Qualité moyenne de remplissage

## 🎨 Fonctionnalités Utiles de Swagger

### 1. Schemas (Modèles de Données)

En bas de la page `/docs`, section **"Schemas"**:

```
┌─────────────────────────────────────────────────────┐
│  📋 Schemas                                         │
│                                                     │
│  ▶ HealthResponse                                  │
│  ▶ ConversionResponse                              │
│  ▶ JobResponse                                     │
│  ▶ BatchResponse                                   │
│  ▶ MetricsResponse                                 │
└─────────────────────────────────────────────────────┘
```

**Cliquez** sur un schema pour voir sa structure complète!

### 2. Codes de Réponse

Chaque endpoint montre les codes HTTP possibles:

```
┌─────────────────────────────────────────────────────┐
│  Responses                                          │
│                                                     │
│  200 ✅ Successful Response                        │
│  400 ⚠️  Bad Request (fichier invalide)           │
│  413 ⚠️  Request Entity Too Large (>50MB)         │
│  422 ⚠️  Validation Error                         │
│  500 ❌ Internal Server Error                      │
└─────────────────────────────────────────────────────┘
```

**Cliquez** sur chaque code pour voir un exemple de réponse!

### 3. Exemples de Code

Pour chaque endpoint, vous pouvez copier des exemples en:

- **curl** (ligne de commande)
- **Python** (requests)
- **JavaScript** (fetch)
- **Node.js** (axios)

Cherchez la section **"Request samples"** ou **"Code samples"**

### 4. Authentification (Si Configurée)

Si l'API nécessite une authentification:

```
┌─────────────────────────────────────────────────────┐
│  [ Authorize ] 🔓                                  │
└─────────────────────────────────────────────────────┘
```

**Cliquez** sur "Authorize" en haut de la page pour configurer vos tokens/clés.

## 🛠️ Astuces et Raccourcis

### Navigation Rapide

- **Ctrl+F / Cmd+F**: Rechercher un endpoint
- **Cliquer** sur un endpoint pour l'ouvrir/fermer
- **Sections colorées**: Organisées par fonctionnalité

### Copier/Coller Efficace

1. **Réponse JSON**: Cliquez sur `{}` pour copier tout
2. **Curl command**: Bouton "Copy" direct
3. **Schema**: Cliquez pour développer et copier

### Tester Plusieurs Fois

Vous pouvez:
- Modifier les paramètres
- Re-cliquer "Execute"
- Comparer les réponses

### Garder un Historique

Swagger UI **ne garde pas** l'historique. Pour sauvegarder:

1. **Copiez** les commandes curl
2. **Sauvegardez** dans un fichier .txt
3. Ou utilisez **Postman** pour importer le schema OpenAPI

## 🔗 Exporter vers Postman/Insomnia

### Récupérer le Schema OpenAPI

1. **Allez** sur: https://pdf-xml-asycuda-api.onrender.com/openapi.json
2. **Copiez** tout le JSON
3. **Sauvegardez** dans un fichier `api-schema.json`

### Importer dans Postman

1. **Postman** → File → Import
2. **Sélectionnez** `api-schema.json`
3. **Postman créera** une collection complète avec tous les endpoints!

### Importer dans Insomnia

1. **Insomnia** → Application → Preferences → Data
2. **Import Data** → From File
3. **Sélectionnez** `api-schema.json`

## 📱 Accès Mobile

Swagger UI fonctionne aussi sur mobile! 📱

**URL**: https://pdf-xml-asycuda-api.onrender.com/docs

**Limitations**:
- Upload de fichiers peut être limité selon le navigateur
- Interface moins confortable sur petit écran
- Préférez un ordinateur pour les tests complexes

## 🎯 Checklist de Test

Avant de mettre en production, testez:

- [ ] Health check fonctionne
- [ ] Conversion simple PDF → XML
- [ ] Conversion asynchrone avec job_id
- [ ] Download du XML généré
- [ ] Batch conversion (2-3 fichiers)
- [ ] Métriques système
- [ ] Temps de réponse acceptable (<5s)
- [ ] Gestion des erreurs (PDF invalide, taille excessive)

## 🆘 Problèmes Courants

### "Failed to fetch"

**Cause**: Service Render en veille (plan gratuit)
**Solution**: Attendez 30 secondes, le service démarre automatiquement

### "413 Request Entity Too Large"

**Cause**: PDF > 50MB
**Solution**: Réduisez la taille du PDF ou contactez l'administrateur

### "422 Validation Error"

**Cause**: Paramètres manquants ou format invalide
**Solution**: Vérifiez les champs requis (marqués avec *)

### "500 Internal Server Error"

**Cause**: Erreur serveur (PDF corrompu, bug)
**Solution**:
1. Essayez avec un autre PDF
2. Vérifiez les logs Render
3. Contactez le support

## 📖 Documentation Complémentaire

- **README.md**: Guide général de l'API
- **README_DEPLOY.md**: Guide de déploiement
- **UPTIMEROBOT_SETUP.md**: Configuration du monitoring

## 🎉 Félicitations!

Vous savez maintenant utiliser Swagger UI pour tester votre API!

**Prochaines étapes:**
1. Testez tous les endpoints
2. Intégrez l'API dans votre application
3. Configurez le monitoring
4. Passez en production! 🚀
