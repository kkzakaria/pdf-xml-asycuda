# Guide de Déploiement sur Render

Guide complet pour configurer et déployer l'API PDF-XML-ASYCUDA sur Render avec la sécurité activée.

## 🎯 Prérequis

- Compte Render (gratuit): https://render.com
- Repository GitHub connecté à Render
- Accès au Dashboard Render

## 🔐 Configuration de la Sécurité sur Render

### Étape 1: Générer une Clé API Sécurisée

Sur votre machine locale:

```bash
# Méthode 1: Python
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Méthode 2: OpenSSL
openssl rand -base64 32

# Méthode 3: Node.js
node -e "console.log(require('crypto').randomBytes(32).toString('base64url'))"
```

**Exemple de clé générée**:
```
xK7_9mPqR2tYvN8zLw3jH4cF6dB1sA5gT0uV-eI9wX2yQ
```

⚠️ **IMPORTANT**: Conservez cette clé en sécurité ! Elle donne accès complet à votre API.

---

### Étape 2: Configurer les Variables d'Environnement sur Render

#### Via le Dashboard Render (Méthode Recommandée)

1. **Accéder au service**:
   - Aller sur https://dashboard.render.com
   - Sélectionner votre service `pdf-xml-asycuda-api`

2. **Naviguer vers Environment**:
   - Cliquer sur **"Environment"** dans le menu de gauche

3. **Ajouter la variable secrète**:
   - Cliquer sur **"Add Environment Variable"**
   - **Key**: `API_KEYS`
   - **Value**: Coller la clé générée à l'étape 1
   - ✅ Cocher **"Secret"** (important !)
   - Cliquer sur **"Save"**

4. **Vérifier les autres variables** (déjà dans render.yaml):
   ```
   ✅ API_REQUIRE_AUTHENTICATION = true
   ✅ API_RATE_LIMIT_ENABLED = true
   ✅ API_CORS_ORIGINS = []
   ```

5. **Sauvegarder et Déployer**:
   - Cliquer sur **"Save Changes"**
   - Render va automatiquement redéployer l'application

---

### Étape 3: Tester le Déploiement

Une fois le déploiement terminé:

```bash
# Récupérer l'URL de votre service Render
RENDER_URL="https://votre-service.onrender.com"

# Test 1: Health check (public, pas d'auth requise)
curl $RENDER_URL/api/v1/health

# Résultat attendu: {"status":"healthy",...}

# Test 2: Conversion sans clé (doit échouer avec 401)
curl $RENDER_URL/api/v1/convert -X POST

# Résultat attendu: {"detail":"API key manquante..."}

# Test 3: Conversion avec clé API (doit fonctionner)
curl -H "X-API-Key: VOTRE_CLE_API" \
     -F "file=@test.pdf" \
     $RENDER_URL/api/v1/convert

# Résultat attendu: {"success":true,"job_id":"conv_..."}
```

---

## 🌐 Configuration CORS pour Frontend

Si vous avez une application frontend qui doit accéder à l'API:

### Méthode 1: Via Dashboard Render

1. Aller dans **Environment**
2. Modifier `API_CORS_ORIGINS`:
   ```json
   ["https://votre-frontend.com","https://app.exemple.com"]
   ```
3. Sauvegarder

### Méthode 2: Via render.yaml

Modifier `render.yaml` localement:

```yaml
- key: API_CORS_ORIGINS
  value: '["https://votre-frontend.com"]'
```

Puis commit et push:

```bash
git add render.yaml
git commit -m "config: Add frontend CORS origin"
git push
```

---

## 🔄 Rotation des Clés API

Pour changer la clé API sans interruption de service:

### Phase 1: Ajouter nouvelle clé

```bash
# Générer nouvelle clé
NEW_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
echo $NEW_KEY
```

**Sur Render Dashboard**:
1. Aller dans Environment
2. Modifier `API_KEYS`
3. Ajouter la nouvelle clé: `ancienne_cle,nouvelle_cle`
4. Sauvegarder (redéploiement automatique)

Les deux clés sont maintenant valides simultanément.

### Phase 2: Distribuer nouvelle clé

- Mettre à jour tous vos clients avec la nouvelle clé
- Tester que tout fonctionne

### Phase 3: Retirer ancienne clé

**Sur Render Dashboard**:
1. Modifier `API_KEYS`
2. Garder seulement: `nouvelle_cle`
3. Sauvegarder

---

## 📊 Monitoring et Logs

### Voir les Logs de Sécurité

Sur Render Dashboard:
1. Aller dans **Logs**
2. Filtrer par:
   - `"authentication_failure"` - Tentatives d'accès sans clé
   - `"path_traversal_attempt"` - Tentatives d'attaque
   - `"ratelimit exceeded"` - Dépassements de rate limit

### Exemples de Logs

```
2025-10-17 13:20:45 - security - WARNING - Tentative d'accès sans API key
  IP: 203.0.113.42
  Path: /api/v1/convert
  Event: authentication_failure

2025-10-17 13:21:12 - slowapi - WARNING - ratelimit 10 per 1 minute exceeded
  IP: 198.51.100.15
  Endpoint: /api/v1/convert
```

---

## 🚨 Alertes de Sécurité

### Configurer Notifications Render

1. **Aller dans Settings** du service
2. **Notifications** → **Add Notification**
3. Configurer:
   - **Type**: Slack / Email / Webhook
   - **Events**: Deploy failed, Service unhealthy

### Surveiller les Métriques

Sur le Dashboard:
- **Requests/minute** - Surveiller les pics inhabituels
- **Error rate** - Augmentation soudaine de 401 = potentielle attaque
- **Response time** - Dégradation = possible DoS

---

## 🛠️ Dépannage

### Problème: "API key manquante" sur tous les appels

**Solution**:
1. Vérifier que `API_KEYS` est bien configurée sur Render
2. Dashboard → Environment → Vérifier présence de `API_KEYS`
3. Si absente, ajouter la variable secrète

### Problème: "API key invalide" avec la bonne clé

**Solutions possibles**:
1. Vérifier qu'il n'y a pas d'espaces avant/après la clé
2. Vérifier que la clé dans Render Dashboard = clé utilisée
3. Logs Render → Vérifier warnings "API key invalide"

### Problème: CORS bloque les requêtes frontend

**Solution**:
1. Dashboard → Environment → `API_CORS_ORIGINS`
2. Ajouter domaine frontend: `["https://votre-frontend.com"]`
3. Sauvegarder et redéployer

### Problème: Rate limit trop restrictif

**Solution**:
Dashboard → Environment → Modifier:
```
API_RATE_LIMIT_UPLOAD = "20/minute"  # au lieu de 10
API_RATE_LIMIT_BATCH = "10/hour"     # au lieu de 5
```

---

## 📋 Checklist de Déploiement Production

### Avant le déploiement

- [ ] Clé API générée (32+ caractères)
- [ ] `API_KEYS` configurée comme **Secret** sur Render
- [ ] `API_REQUIRE_AUTHENTICATION = true`
- [ ] CORS configuré avec domaines spécifiques (pas `["*"]`)
- [ ] Rate limiting activé
- [ ] Tests de sécurité passés localement

### Après le déploiement

- [ ] Health check fonctionne: `GET /api/v1/health`
- [ ] Auth bloque requêtes sans clé: `POST /api/v1/convert` → 401
- [ ] Auth autorise avec clé valide: avec `X-API-Key` → 200
- [ ] Logs de sécurité visibles sur Render Dashboard
- [ ] Documentation utilisateur mise à jour avec URL API

### Monitoring continu

- [ ] Surveiller erreurs 401 (tentatives non autorisées)
- [ ] Surveiller erreurs 429 (rate limiting)
- [ ] Vérifier logs de sécurité quotidiennement
- [ ] Rotation clés API tous les 3-6 mois

---

## 🔗 Ressources

- **Dashboard Render**: https://dashboard.render.com
- **Documentation Render**: https://render.com/docs
- **Variables d'environnement**: https://render.com/docs/environment-variables
- **Logs**: https://render.com/docs/logs
- **API Health Check**: `https://votre-service.onrender.com/api/v1/health`
- **API Documentation**: `https://votre-service.onrender.com/docs`

---

## 🎯 Exemple de Configuration Complète

### render.yaml (public)
```yaml
envVars:
  - key: API_REQUIRE_AUTHENTICATION
    value: true
  - key: API_CORS_ORIGINS
    value: '["https://mon-frontend.com"]'
  - key: API_RATE_LIMIT_ENABLED
    value: true
```

### Dashboard Render (secrets)
```
API_KEYS = "xK7_9mPqR2tYvN8zLw3jH4cF6dB1sA5gT0uV-eI9wX2yQ" (SECRET)
```

### Code Client (JavaScript)
```javascript
const API_URL = "https://mon-api.onrender.com";
const API_KEY = "xK7_9mPqR2tYvN8zLw3jH4cF6dB1sA5gT0uV-eI9wX2yQ";

fetch(`${API_URL}/api/v1/convert`, {
  method: "POST",
  headers: {
    "X-API-Key": API_KEY
  },
  body: formData
});
```

---

**Dernière mise à jour**: 2025-10-17
**Version API**: 1.1.0 (avec sécurité)
