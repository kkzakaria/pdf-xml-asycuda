# Configuration de l'Environnement GitHub 'render'

## ⚠️ Configuration Actuelle à Corriger

Vous avez créé:
- ✅ `RENDER_SERVICE_ID` comme **secret d'environnement** (CORRECT)
- ❌ `RENDER_API_KEY` comme **variable d'environnement** (INCORRECT - doit être un secret!)

### Pourquoi RENDER_API_KEY doit être un secret?

Les clés API sont des informations sensibles qui donnent accès à votre service Render. Si elles sont exposées comme variables d'environnement:
- ⚠️ Elles apparaissent en clair dans les logs GitHub Actions
- ⚠️ N'importe qui avec accès au repo peut les voir
- ⚠️ Risque de compromission de votre service Render

## 🔧 Correction Requise

### Étape 1: Supprimer la Variable d'Environnement

1. Aller sur: https://github.com/kkzakaria/pdf-xml-asycuda/settings/environments
2. Cliquer sur l'environnement **render**
3. Dans la section **Environment variables**, supprimer `RENDER_API_KEY`

### Étape 2: Créer le Secret d'Environnement

1. Sur la même page (environnement **render**)
2. Dans la section **Environment secrets**, cliquer sur **Add secret**
3. Ajouter:
   - **Name**: `RENDER_API_KEY`
   - **Value**: Votre clé API Render (commence par `rnd_...`)
4. Cliquer sur **Add secret**

### Étape 3: Vérifier la Configuration Finale

Après correction, votre environnement **render** doit avoir:

**Environment secrets** (🔒 Masqués):
- ✅ `RENDER_API_KEY`
- ✅ `RENDER_SERVICE_ID`

**Environment variables** (👁️ Visibles):
- (Aucune - toutes les valeurs sensibles doivent être des secrets)

## ✅ Configuration Correcte

### Dans GitHub

**Settings → Environments → render**:

```yaml
Environment secrets:
  - RENDER_API_KEY: rnd_xxxxxxxxxxxxxxxxxxxxx (🔒 masqué)
  - RENDER_SERVICE_ID: srv-xxxxxxxxxxxxxxxxxxxxx (🔒 masqué)

Environment variables:
  (vide - pas de variables non sensibles)
```

### Dans le Workflow

Le workflow `.github/workflows/deploy-render.yml` référence maintenant l'environnement:

```yaml
jobs:
  deploy:
    name: Trigger Render Deploy
    runs-on: ubuntu-latest
    environment: render  # ← Utilise l'environnement 'render'

    steps:
      - name: Deploy to Render
        env:
          RENDER_API_KEY: ${{ secrets.RENDER_API_KEY }}
          RENDER_SERVICE_ID: ${{ secrets.RENDER_SERVICE_ID }}
```

## 🧪 Test de la Configuration

Une fois corrigé, tester avec:

```bash
# Créer un tag de test
git tag v1.4.8-test
git push origin v1.4.8-test
```

**Vérifications dans GitHub Actions**:

1. **Workflow "Docker Build & Push"** doit réussir
2. **Workflow "Deploy to Render"** doit:
   - ✅ Utiliser l'environnement `render`
   - ✅ Appeler l'API Render avec succès
   - ✅ Afficher "✅ Redéploiement déclenché avec succès!"
   - ❌ NE PAS afficher la clé API en clair (elle doit être masquée: `***`)

3. **Dashboard Render** doit montrer un nouveau déploiement

## 🔍 Vérification de Sécurité

Dans les logs GitHub Actions, vous devez voir:

```bash
✅ BON - Clé API masquée:
🔄 Déclenchement du redéploiement via API Render...
Authorization: Bearer ***

❌ MAUVAIS - Clé API visible:
Authorization: Bearer rnd_xxxxxxxxxxxxxxxxxxxxx
```

Si vous voyez la clé en clair, c'est que RENDER_API_KEY est toujours une variable au lieu d'un secret!

## 📊 Différence Variables vs Secrets

| Aspect | Variables d'Environnement | Secrets d'Environnement |
|--------|---------------------------|-------------------------|
| Visibilité | 👁️ Visibles dans les logs | 🔒 Masqués (***) |
| Sécurité | ⚠️ Accessible en lecture | 🔒 Protégé |
| Usage | Configurations publiques | Clés API, tokens, mots de passe |
| Exemple | `API_URL`, `ENVIRONMENT` | `API_KEY`, `TOKEN`, `PASSWORD` |

## ❓ FAQ

**Q: Pourquoi deux secrets alors qu'avant on n'en avait pas?**
R: Avant, Render utilisait `autoDeploy: true` qui détectait automatiquement les changements (mais lent). Maintenant, on utilise l'API Render pour forcer le déploiement immédiatement.

**Q: Que se passe-t-il si je ne corrige pas?**
R: Le déploiement fonctionnera toujours grâce au fallback automatique de Render, mais:
- ⚠️ Votre clé API sera visible dans les logs GitHub
- ⚠️ Risque de sécurité
- ⚠️ Le déploiement sera plus lent (détection automatique au lieu de déclenchement forcé)

**Q: Comment obtenir RENDER_API_KEY?**
R: https://dashboard.render.com/u/settings → API Keys → Create API Key

**Q: Comment obtenir RENDER_SERVICE_ID?**
R: Dashboard Render → Votre service → L'ID est dans l'URL: `srv-xxxxxxxxxxxxxxxxxxxxx`

## 🔗 Liens Utiles

- [GitHub Environments Documentation](https://docs.github.com/en/actions/deployment/targeting-different-environments/using-environments-for-deployment)
- [GitHub Secrets Documentation](https://docs.github.com/en/actions/security-guides/encrypted-secrets)
- [Render API Documentation](https://api-docs.render.com)
