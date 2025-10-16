# Guide de Déploiement - Render

Ce guide explique comment déployer l'API PDF-XML-ASYCUDA sur Render.

## 📋 Prérequis

1. Compte GitHub (déjà configuré ✅)
2. Compte Render (gratuit) - [Créer un compte](https://dashboard.render.com/register)
3. Images Docker publiées sur ghcr.io (déjà disponibles ✅)

## 🚀 Déploiement Initial

### Option 1: Déploiement Automatique (Recommandé)

1. **Connectez-vous à Render**
   - Allez sur https://dashboard.render.com
   - Connectez-vous avec votre compte GitHub

2. **Créez un nouveau Blueprint**
   - Cliquez sur "New +" → "Blueprint"
   - Sélectionnez votre repository `kkzakaria/pdf-xml-asycuda`
   - Render détectera automatiquement le fichier `render.yaml`
   - Cliquez sur "Apply"

3. **Configuration**
   - Render créera automatiquement le service web
   - L'application sera déployée depuis l'image Docker ghcr.io
   - Un URL public sera généré (ex: `https://pdf-xml-asycuda-api.onrender.com`)

4. **Vérification**
   - Attendez que le déploiement soit terminé (~2-3 minutes)
   - Testez l'API: `https://votre-app.onrender.com/api/v1/health`
   - Documentation interactive: `https://votre-app.onrender.com/docs`

### Option 2: Déploiement Manuel

1. **Créer un Web Service**
   - Dashboard Render → "New +" → "Web Service"
   - Sélectionnez "Deploy an existing image from a registry"

2. **Configuration de l'Image**
   ```
   Image URL: ghcr.io/kkzakaria/pdf-xml-asycuda:latest
   ```

3. **Configuration du Service**
   - Name: `pdf-xml-asycuda-api`
   - Region: `Frankfurt` (ou plus proche de vous)
   - Instance Type: `Free`

4. **Variables d'Environnement**
   Copiez les variables depuis `render.yaml` ou utilisez les valeurs par défaut.

## 📊 Plans Render

### Free Plan (Gratuit)
- ✅ Parfait pour débuter et tester
- ✅ 750 heures/mois (suffisant pour un service)
- ✅ SSL automatique
- ✅ Déploiement automatique depuis GitHub
- ⚠️ Service en veille après 15 min d'inactivité (redémarre en ~30s)
- ⚠️ Stockage éphémère (fichiers perdus au redémarrage)
- ⚠️ 512 MB RAM

### Starter Plan ($7/mois) - Recommandé pour Production
- ✅ Pas de mise en veille
- ✅ 512 MB RAM persistante
- ✅ Stockage persistant (disque de 1GB+)
- ✅ Meilleure performance

### Standard Plan ($25/mois) - Production intensive
- ✅ 2 GB RAM
- ✅ Scaling horizontal
- ✅ Meilleure disponibilité

## 🔧 Configuration Avancée

### Stockage Persistant (Starter plan+)

Si vous avez besoin de conserver les fichiers uploads/outputs entre redémarrages:

1. Modifiez `render.yaml` et décommentez:
```yaml
disk:
  name: pdf-storage
  mountPath: /app/data
  sizeGB: 1
```

2. Mettez à jour les variables d'environnement:
```yaml
- key: API_UPLOAD_DIR
  value: /app/data/uploads

- key: API_OUTPUT_DIR
  value: /app/data/output
```

### Domaine Personnalisé

1. Dans le dashboard Render, allez dans votre service
2. Settings → Custom Domain
3. Ajoutez votre domaine (ex: `api.monsite.com`)
4. Configurez le DNS selon les instructions Render

### Mise à l'Échelle

Pour augmenter les ressources:
```yaml
numInstances: 2  # Plusieurs instances (load balancing)
plan: starter    # ou standard, pro
```

## 🔄 Déploiement Continu

### Déploiement Automatique Activé ✅

Render redéploiera automatiquement à chaque:
- Push sur la branche `main`
- Nouvelle release (tag `v*.*.*`)
- Nouvelle image Docker publiée

### Workflow GitHub Actions

Le workflow `.github/workflows/docker.yml` publie automatiquement:
1. Les images Docker sur ghcr.io
2. Render détecte la nouvelle image
3. Redéploiement automatique

## 📈 Monitoring

### Logs en Temps Réel

```bash
# Via le dashboard Render
Dashboard → Votre service → Logs

# Via Render CLI
render logs -s pdf-xml-asycuda-api --tail
```

### Métriques

- Dashboard → Votre service → Metrics
- CPU, Mémoire, Requêtes HTTP
- Temps de réponse

### Health Checks

Render vérifie automatiquement `/api/v1/health` toutes les 30 secondes.

## 🧪 Tests de Déploiement

### Test de l'API

```bash
# Remplacez YOUR_APP_URL par votre URL Render
export API_URL="https://pdf-xml-asycuda-api.onrender.com"

# Health check
curl $API_URL/api/v1/health

# Test conversion
curl -X POST "$API_URL/api/v1/convert" \
  -F "file=@tests/DOSSIER_18236.pdf"

# Documentation interactive
open $API_URL/docs
```

### Test de Performance

```bash
# Test de charge basique
for i in {1..10}; do
  curl -X GET $API_URL/api/v1/health &
done
wait
```

## 🔒 Sécurité

### Variables d'Environnement Sensibles

Si vous avez besoin d'ajouter des secrets (API keys, tokens):

1. Dashboard → Service → Environment
2. Ajoutez des variables avec l'icône 🔒 (secret)
3. Ces variables ne seront pas visibles dans les logs

### CORS Configuration

Par défaut, CORS est ouvert (`["*"]`). Pour production:

```yaml
- key: API_CORS_ORIGINS
  value: '["https://monsite.com", "https://www.monsite.com"]'
```

## ⚡ Optimisation Performance

### Plan Gratuit

```yaml
- key: API_DEFAULT_WORKERS
  value: 2

- key: API_MAX_WORKERS
  value: 4
```

### Plans Payants

```yaml
- key: API_DEFAULT_WORKERS
  value: 4

- key: API_MAX_WORKERS
  value: 8
```

## 🚨 Dépannage

### Service en Veille (Free Plan)

**Symptôme**: Première requête lente (~30s)
**Solution**:
- Utiliser un service de ping (UptimeRobot, Freshping)
- Ou upgrader vers Starter plan

### Erreur 502 Bad Gateway

**Cause**: Service en cours de démarrage
**Solution**: Attendre 1-2 minutes

### Uploads Échouent

**Cause**: Limite de taille dépassée
**Solution**: Augmenter `API_MAX_UPLOAD_SIZE` ou plan Render

### Mémoire Insuffisante

**Symptôme**: Service redémarre fréquemment
**Solution**:
- Réduire `API_MAX_WORKERS`
- Ou upgrader vers Starter/Standard plan

## 📞 Support

- **Render Docs**: https://render.com/docs
- **Render Community**: https://community.render.com
- **Render Status**: https://status.render.com

## 🔗 Liens Utiles

- [Dashboard Render](https://dashboard.render.com)
- [Documentation Render](https://render.com/docs)
- [Blueprint Spec](https://render.com/docs/blueprint-spec)
- [Pricing](https://render.com/pricing)

## 📝 Checklist de Déploiement

- [ ] Compte Render créé et connecté à GitHub
- [ ] Blueprint appliqué depuis render.yaml
- [ ] Service déployé et running
- [ ] Health check passe (GET /api/v1/health)
- [ ] Test de conversion réussi
- [ ] Documentation accessible (/docs)
- [ ] URL partagée avec l'équipe
- [ ] (Optionnel) Domaine personnalisé configuré
- [ ] (Optionnel) Monitoring configuré
- [ ] (Optionnel) Upgrade vers plan payant si nécessaire
