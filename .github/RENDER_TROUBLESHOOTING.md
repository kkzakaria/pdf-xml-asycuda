# Dépannage du Déploiement Render

## 🔍 Situation Actuelle

### ✅ Succès
- Workflow GitHub Actions: **SUCCESS**
- Image Docker construite: **SUCCESS** (`ghcr.io/kkzakaria/pdf-xml-asycuda:latest`)
- API Render appelée: **SUCCESS** (Deployment ID: `dep-d3tpio3uibrs73barr3g`)

### ❌ Problème
- Le service Render **n'a PAS redémarré**
- Version de l'API: **1.1.0** (au lieu de 1.4.0 ou 1.4.8-test)
- Uptime: **21+ minutes** (indique qu'il n'y a pas eu de redémarrage)

## 🔍 Étapes de Diagnostic

### 1. Vérifier le Dashboard Render

**URL**: https://dashboard.render.com

**Navigation**:
1. Trouver votre service: **pdf-xml-asycuda-api**
2. Cliquer sur l'onglet **"Events"** ou **"Deploys"**
3. Chercher le déploiement récent avec ID: `dep-d3tpio3uibrs73barr3g`

**Statuts possibles**:

#### ✅ En cours (In Progress)
```
Status: Building / Deploying
Message: Pulling image from registry...
```
→ **Action**: Attendre que le déploiement se termine

#### ❌ Échec (Failed)
```
Status: Deploy failed
Message: Health check failed / Build error / etc.
```
→ **Action**: Consulter les logs d'erreur (voir section ci-dessous)

#### ⏸️ En attente (Queued)
```
Status: Queued
Message: Waiting for available resources...
```
→ **Action**: Attendre (le plan free a des limites de concurrence)

#### ⚠️ Pas visible
Le déploiement n'apparaît pas du tout
→ **Action**: Vérifier RENDER_SERVICE_ID (section ci-dessous)

### 2. Consulter les Logs Render

**Dans le Dashboard Render**:
1. Service → **Logs**
2. Chercher des messages récents (vers 15:21 UTC)

**Messages à surveiller**:

#### ✅ Succès
```
Pulling image ghcr.io/kkzakaria/pdf-xml-asycuda:latest
Image pulled successfully
Starting service...
Health check passed
Service is live
```

#### ❌ Erreurs communes

**Erreur: Image non trouvée**
```
Error: Failed to pull image
Error: manifest not found
```
→ **Cause**: L'image n'existe pas ou n'est pas publique
→ **Solution**: Vérifier que l'image sur GHCR est publique

**Erreur: Health check échoué**
```
Health check failed
GET /api/v1/health returned 502/503/504
```
→ **Cause**: L'application ne démarre pas correctement
→ **Solution**: Tester l'image localement

**Erreur: Pull rate limit**
```
Error: toomanyrequests: You have reached your pull rate limit
```
→ **Cause**: Limite Docker Hub/GHCR atteinte
→ **Solution**: Attendre ou configurer authentication

### 3. Vérifier les Secrets

**URL**: https://github.com/kkzakaria/pdf-xml-asycuda/settings/environments

**Environnement `render`**:
- ✅ `RENDER_API_KEY`: Doit être un **secret** (masqué)
- ✅ `RENDER_SERVICE_ID`: Doit être un **secret** (masqué)

**Vérification de RENDER_SERVICE_ID**:
1. Dashboard Render → Votre service
2. L'URL contient: `https://dashboard.render.com/web/srv-xxxxxxxxxxxxxxxxxxxxx`
3. Le `srv-xxxxxxxxxxxxxxxxxxxxx` est votre SERVICE_ID
4. Comparer avec la valeur dans GitHub Secrets

### 4. Vérifier l'Image Docker

**Vérifier que l'image :latest existe et est à jour**:

```bash
# Vérifier l'image sur GHCR
docker pull ghcr.io/kkzakaria/pdf-xml-asycuda:latest
docker inspect ghcr.io/kkzakaria/pdf-xml-asycuda:latest | grep Created

# Comparer avec l'image du tag
docker pull ghcr.io/kkzakaria/pdf-xml-asycuda:v1.4.8-test
docker inspect ghcr.io/kkzakaria/pdf-xml-asycuda:v1.4.8-test | grep Created

# Les deux dates doivent être identiques (même build)
```

**Vérifier que l'image est publique**:
1. Aller sur: https://github.com/kkzakaria/pdf-xml-asycuda/pkgs/container/pdf-xml-asycuda
2. Vérifier la visibilité: doit être **Public**
3. Si Private: Settings → Change visibility → Public

### 5. Tester l'Image Localement

```bash
# Pull l'image :latest
docker pull ghcr.io/kkzakaria/pdf-xml-asycuda:latest

# Démarrer le conteneur
docker run -p 8000:8000 \
  -e API_VERSION=1.4.8-test \
  ghcr.io/kkzakaria/pdf-xml-asycuda:latest

# Vérifier la version
curl http://localhost:8000/api/v1/health

# Attendu:
# {"status":"healthy","version":"1.4.8-test",...}
```

## 🔧 Solutions par Problème

### Problème 1: Déploiement en attente (Free Tier)

**Symptôme**: Déploiement `dep-d3tpio3uibrs73barr3g` en status "Queued"

**Cause**: Le plan free de Render limite la concurrence de déploiement

**Solutions**:
1. ⏳ **Attendre** (peut prendre 10-30 minutes sur free tier)
2. 💰 **Upgrade** vers un plan payant (déploiements instantanés)
3. 🔄 **Redéployer manuellement** via le dashboard Render

### Problème 2: Health Check échoue

**Symptôme**: Render tire l'image mais le service ne démarre pas

**Diagnostic**:
```bash
# Tester l'image localement
docker run -p 8000:8000 ghcr.io/kkzakaria/pdf-xml-asycuda:latest

# Vérifier le health check
curl http://localhost:8000/api/v1/health
```

**Solutions**:
- Si l'image fonctionne localement mais pas sur Render → Vérifier les variables d'environnement dans `render.yaml`
- Si l'image ne fonctionne pas localement → Bug dans le code ou Dockerfile

### Problème 3: Render ne détecte pas le changement

**Symptôme**: API appelée avec succès mais Render ne tire pas l'image

**Cause**: Render cache l'image avec le même digest

**Solution**: Forcer Render à retirer l'image avec `clearCache: "clear"`

**Vérification**:
```bash
# Vérifier que le workflow utilise clearCache
grep -A 5 "clearCache" .github/workflows/deploy-render.yml

# Attendu:
# -d '{"clearCache":"clear"}'
```

### Problème 4: IMAGE_TAG versionné au lieu de :latest

**Symptôme**: Le workflow essaie de déployer `:v1.4.8-test` au lieu de `:latest`

**Cause**: La logique de détection du tag ne fonctionne pas correctement

**Solution**: Vérifier que `render.yaml` pointe vers `:latest`:
```yaml
services:
  - type: web
    image:
      url: ghcr.io/kkzakaria/pdf-xml-asycuda:latest  # ← Doit être :latest
```

### Problème 5: API_VERSION hardcodée

**Symptôme**: Render redéploie mais la version reste 1.1.0

**Cause**: `API_VERSION` est hardcodée à 1.4.0 dans `render.yaml`

**Explication**:
- L'API retourne `version: 1.1.0` car c'est ce qui est codé dans l'ancienne image
- La nouvelle image devrait retourner `1.4.0` (ou la valeur de render.yaml)

**Vérification**:
```bash
# Vérifier la version dans render.yaml
grep -A 1 "API_VERSION" render.yaml

# Devrait afficher:
# - key: API_VERSION
#   value: 1.4.0
```

**Note**: La version dans le health check vient du code de l'application, pas de la variable d'environnement seule.

## 📋 Checklist Complète

- [ ] Dashboard Render vérifié (déploiement visible?)
- [ ] Logs Render consultés (erreurs?)
- [ ] Secrets GitHub vérifiés (RENDER_API_KEY, RENDER_SERVICE_ID)
- [ ] Image :latest existe sur GHCR
- [ ] Image est publique sur GHCR
- [ ] Image testée localement (fonctionne?)
- [ ] render.yaml pointe vers :latest
- [ ] Health check endpoint fonctionne

## 🔗 Liens Utiles

- **Dashboard Render**: https://dashboard.render.com
- **GHCR Packages**: https://github.com/kkzakaria/pdf-xml-asycuda/pkgs/container/pdf-xml-asycuda
- **GitHub Actions**: https://github.com/kkzakaria/pdf-xml-asycuda/actions
- **Workflow Deploy**: https://github.com/kkzakaria/pdf-xml-asycuda/actions/runs/18784225091
- **Render API Docs**: https://api-docs.render.com/reference/create-deploy

## 📊 Prochaines Étapes

### Option A: Déploiement Manuel (Rapide)
1. Aller sur Dashboard Render → Service
2. Cliquer sur **"Manual Deploy"** → **"Clear build cache & deploy"**
3. Attendre 2-3 minutes
4. Vérifier: `curl https://pdf-xml-asycuda-api.onrender.com/api/v1/health`

### Option B: Debug Approfondi (Complet)
1. Suivre la checklist ci-dessus
2. Identifier la cause exacte
3. Corriger le problème
4. Retester avec un nouveau tag

### Option C: Revenir au Déploiement Manuel
1. Désactiver l'API Render dans le workflow
2. Laisser Render détecter automatiquement les changements (plus lent mais fiable)
3. Supprimer les secrets GitHub
