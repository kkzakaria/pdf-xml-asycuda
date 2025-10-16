# Guide de Configuration UptimeRobot

Ce guide vous montre comment configurer UptimeRobot pour maintenir votre service Render actif 24/7 gratuitement.

## 🎯 Objectif

Empêcher votre service Render (plan gratuit) de se mettre en veille en le "pingant" toutes les 5 minutes.

## 📋 Étapes de Configuration

### Étape 1: Créer un Compte UptimeRobot

1. **Allez sur UptimeRobot**
   - URL: https://uptimerobot.com/
   - Cliquez sur "Register" (inscription gratuite)

2. **Remplissez le formulaire**
   ```
   Email: votre-email@example.com
   Password: [choisissez un mot de passe sécurisé]
   ```

3. **Validez votre email**
   - Vérifiez votre boîte mail
   - Cliquez sur le lien de confirmation

4. **Connectez-vous au Dashboard**
   - URL: https://uptimerobot.com/dashboard

### Étape 2: Récupérer l'URL de votre Service Render

1. **Dans le Dashboard Render**
   - URL: https://dashboard.render.com
   - Cliquez sur votre service `pdf-xml-asycuda-api`

2. **Copiez l'URL publique**
   - Format: `https://pdf-xml-asycuda-api.onrender.com`
   - OU: `https://pdf-xml-asycuda-api-XXXX.onrender.com`

3. **Testez l'URL dans votre navigateur**
   ```
   https://votre-url.onrender.com/api/v1/health
   ```
   - Vous devriez voir: `{"status":"ok",...}`

### Étape 3: Créer un Monitor sur UptimeRobot

1. **Dans le Dashboard UptimeRobot**
   - Cliquez sur **"+ Add New Monitor"** (bouton orange en haut)

2. **Configurez le Monitor**

   **Monitor Type:**
   ```
   ☑ HTTP(s)
   ```

   **Friendly Name:**
   ```
   PDF-XML-ASYCUDA API - Health Check
   ```

   **URL (or IP):**
   ```
   https://votre-url.onrender.com/api/v1/health
   ```
   ⚠️ **Important**: Remplacez `votre-url.onrender.com` par votre vraie URL Render

   **Monitoring Interval:**
   ```
   ☑ 5 minutes
   ```
   ℹ️ C'est l'intervalle minimum gratuit (suffisant pour éviter la veille)

3. **Paramètres Avancés (Optionnel)**

   Cliquez sur **"Advanced Settings"** pour configurer:

   **HTTP Method:**
   ```
   ☑ GET (par défaut)
   ```

   **Keyword (optionnel mais recommandé):**
   ```
   Keyword Type: ☑ Exists
   Keyword Value: "status"
   ```
   ℹ️ Cela vérifie que la réponse contient le mot "status" (plus fiable)

   **Alert Contacts:**
   ```
   ☑ [Votre email] (déjà configuré par défaut)
   ```
   ℹ️ Vous recevrez une notification si l'API est down

4. **Créez le Monitor**
   - Cliquez sur **"Create Monitor"** (bouton vert en bas)

### Étape 4: Vérifier la Configuration

1. **Vérifiez le Status**
   - Dans le dashboard, vous verrez votre nouveau monitor
   - Status doit être: 🟢 **Up**
   - Si ⚠️ "Waiting for first check", attendez 5 minutes

2. **Vérifiez les Statistiques**
   - Cliquez sur le monitor
   - Vous verrez:
     - Response Time (temps de réponse)
     - Uptime Ratio (taux de disponibilité)
     - Logs des checks

### Étape 5: Configuration des Alertes (Optionnel)

1. **Configurez les Notifications**
   - Dashboard → **"My Settings"** → **"Alert Contacts"**

2. **Ajoutez des contacts supplémentaires**
   - Email (déjà configuré)
   - SMS (premium)
   - Slack webhook
   - Discord webhook
   - Telegram

3. **Configuration Slack (Bonus)**

   Si vous utilisez Slack:

   a. Dans Slack, créez un Incoming Webhook:
      - https://api.slack.com/messaging/webhooks
      - Choisissez un channel (ex: #monitoring)
      - Copiez l'URL du webhook

   b. Dans UptimeRobot:
      - My Settings → Alert Contacts
      - Add Alert Contact → Webhook
      - URL: [collez votre Slack webhook URL]
      - Post Value: `{"text":"Monitor: *monitorFriendlyName* is *monitorAlertType*"}`

## ✅ Résultat Final

Une fois configuré:

- ✅ Votre API Render sera "pingée" toutes les 5 minutes
- ✅ Le service ne se mettra JAMAIS en veille
- ✅ Vous recevrez des alertes si l'API est down
- ✅ Dashboard de monitoring gratuit avec statistiques

## 📊 Monitoring Supplémentaire (Bonus)

### Ajouter d'autres Endpoints à Monitorer

Vous pouvez créer plusieurs monitors pour différents endpoints:

1. **Health Check** (déjà fait)
   ```
   https://votre-url.onrender.com/api/v1/health
   ```

2. **Documentation API**
   ```
   https://votre-url.onrender.com/docs
   ```

3. **Metrics Endpoint**
   ```
   https://votre-url.onrender.com/api/v1/metrics
   ```

### Limites du Plan Gratuit

- ✅ **50 monitors** (largement suffisant)
- ✅ **5 minutes** d'intervalle minimum
- ✅ **Alertes email** illimitées
- ✅ **Statistiques** sur 90 jours
- ✅ **Status pages** publiques

## 🔧 Configuration Avancée

### Status Page Public (Optionnel)

Créez une page publique pour afficher le statut de votre API:

1. **Dashboard UptimeRobot** → **"Status Pages"**
2. **Add New Status Page**
3. **Configurez:**
   ```
   Friendly Name: PDF-XML-ASYCUDA Status
   Select Monitors: ☑ PDF-XML-ASYCUDA API
   Custom Domain: (optionnel)
   ```
4. **Partagez le lien**:
   ```
   https://stats.uptimerobot.com/XXXXX
   ```

### Badge de Status pour GitHub

Ajoutez un badge de status dans votre README:

1. **Dans Status Page Settings**
   - Copiez le badge code

2. **Ajoutez au README.md:**
   ```markdown
   [![API Status](https://img.shields.io/uptimerobot/status/mXXXXXXXXX?label=API%20Status)](https://stats.uptimerobot.com/XXXXX)
   ```

## 🐛 Dépannage

### Monitor Status: "Down"

**Causes possibles:**
- Service Render en cours de déploiement
- URL incorrecte
- Endpoint health check non disponible

**Solutions:**
1. Vérifiez l'URL dans votre navigateur
2. Vérifiez les logs Render
3. Attendez 2-3 minutes (déploiement)

### Monitor Status: "Seems Down"

**Cause:**
- Cold start trop long (>30s timeout)

**Solution:**
- Augmentez le timeout dans Advanced Settings:
  ```
  Timeout: 60 seconds
  ```

### Pas de Notifications

**Vérifiez:**
1. Alert Contacts sont configurés
2. Monitor a "Alert Contacts" assignés
3. Email n'est pas dans spam

## 📈 Statistiques à Surveiller

Dans le dashboard UptimeRobot, surveillez:

- **Uptime Ratio**: Doit être >99%
- **Average Response Time**:
  - First request (cold): ~1000-2000ms
  - Subsequent: ~200-500ms
- **Down Events**: Doit être 0 ou très rare

## 🎓 Conseils Pro

1. **Nommez clairement vos monitors**
   - Format: `[Projet] - [Service] - [Endpoint]`
   - Ex: `PDF-ASYCUDA - API - Health Check`

2. **Utilisez des keywords**
   - Plus fiable que juste le status code HTTP
   - Vérifie que la réponse est correcte

3. **Configurez plusieurs monitors**
   - Health check (toutes les 5 min)
   - Endpoints critiques (toutes les 5 min)

4. **Consultez régulièrement**
   - Vérifiez les stats une fois par semaine
   - Identifiez les patterns de downtime

## 🔗 Liens Utiles

- **Dashboard UptimeRobot**: https://uptimerobot.com/dashboard
- **Documentation**: https://uptimerobot.com/help
- **API UptimeRobot**: https://uptimerobot.com/api (si vous voulez automatiser)
- **Status Page**: https://stats.uptimerobot.com/

## ✨ Résumé

**Ce que vous avez maintenant:**
- ✅ Service Render déployé et actif 24/7
- ✅ Monitoring automatique toutes les 5 minutes
- ✅ Alertes en cas de problème
- ✅ Statistiques de disponibilité
- ✅ Coût: $0/mois

**Total épargné: $7/mois** (vs plan Render Starter)

---

**Besoin d'aide?** N'hésitez pas à demander!
