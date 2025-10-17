# Plateforme d'Acquisition de Clés API - Recommandations

**Document de planification pour l'évolution de la gestion des clés API**

---

## 🎯 Vision

Permettre aux utilisateurs de s'inscrire en self-service et d'obtenir leurs propres clés API pour utiliser le service de conversion PDF → XML ASYCUDA.

---

## 📋 État Actuel (v1.1.0)

### Configuration Actuelle
- **Authentification**: Clé API unique partagée
- **Gestion**: Manuelle via administrateur
- **Distribution**: Contact direct avec l'administrateur
- **Message Swagger UI**: "Veuillez contacter l'administrateur du service"

### Limitations
- ❌ Pas de self-service pour les utilisateurs
- ❌ Pas de tracking individuel par utilisateur
- ❌ Pas de quotas personnalisés
- ❌ Pas de facturation automatisée
- ❌ Difficulté à gérer de nombreux utilisateurs

---

## 🚀 Solution Recommandée: Plateforme de Gestion API Keys

### Architecture Proposée

```
┌─────────────────────────────────────────────────────────┐
│              Plateforme Web (Frontend)                  │
│  - Inscription / Login                                  │
│  - Tableau de bord utilisateur                          │
│  - Génération de clés API                               │
│  - Monitoring d'utilisation                             │
│  - Documentation interactive                            │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│         API de Gestion (Backend)                        │
│  - Authentification utilisateurs (OAuth2/JWT)           │
│  - Gestion des clés API                                 │
│  - Tracking d'utilisation                               │
│  - Quotas et rate limiting personnalisés                │
│  - Facturation (optionnel)                              │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│       Base de Données (PostgreSQL/MongoDB)              │
│  - Users (id, email, plan, created_at, ...)            │
│  - API Keys (key_id, user_id, key_hash, expires_at)    │
│  - Usage Stats (user_id, endpoint, count, timestamp)   │
│  - Plans (plan_id, name, quota_limit, price)           │
└─────────────────────────────────────────────────────────┘
```

---

## 🛠️ Stack Technologique Recommandé

### Option 1: Solution Complète avec Auth0 + Stripe
**Avantages**: Rapide à mettre en place, gestion auth professionnelle
**Coût**: ~$25/mois (Auth0 Essential) + 2.9% par transaction (Stripe)

**Stack**:
- **Frontend**: Next.js + Tailwind CSS + Shadcn UI
- **Backend**: FastAPI (extension de l'API actuelle)
- **Auth**: Auth0 (authentification clé en main)
- **Paiement**: Stripe (si facturation nécessaire)
- **Database**: PostgreSQL sur Render
- **Hosting**: Vercel (frontend) + Render (backend)

### Option 2: Solution Open-Source Complète
**Avantages**: Contrôle total, pas de coûts récurrents tiers
**Coût**: Temps de développement plus élevé

**Stack**:
- **Frontend**: Next.js + NextAuth.js + React Query
- **Backend**: FastAPI + SQLAlchemy
- **Database**: PostgreSQL
- **Hosting**: Render (tout-en-un)

### Option 3: API Gateway Managé (AWS/GCP)
**Avantages**: Scalabilité automatique, fonctionnalités entreprise
**Coût**: Variable selon usage (~$3.50/million de requêtes)

**Services**:
- **AWS API Gateway** + Lambda + Cognito + DynamoDB
- **GCP API Gateway** + Cloud Functions + Firebase Auth

---

## 📐 Modèle de Données

### Table `users`
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),
    password_hash VARCHAR(255),  -- Si pas OAuth
    plan_id INTEGER REFERENCES plans(id),
    created_at TIMESTAMP DEFAULT NOW(),
    last_login TIMESTAMP,
    is_active BOOLEAN DEFAULT true,
    email_verified BOOLEAN DEFAULT false
);
```

### Table `api_keys`
```sql
CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    key_prefix VARCHAR(20),  -- ex: "sk_live_AbC..."
    key_hash VARCHAR(255),   -- Hash de la clé complète
    name VARCHAR(100),        -- "Production Key", "Dev Key"
    scopes JSONB,            -- Permissions spécifiques
    created_at TIMESTAMP DEFAULT NOW(),
    last_used_at TIMESTAMP,
    expires_at TIMESTAMP,
    is_active BOOLEAN DEFAULT true,
    UNIQUE(key_prefix)
);
```

### Table `plans`
```sql
CREATE TABLE plans (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,  -- "Free", "Starter", "Pro"
    quota_monthly INTEGER,              -- Nombre de conversions/mois
    rate_limit_per_minute INTEGER,
    max_file_size_mb INTEGER,
    price_monthly DECIMAL(10,2),
    features JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Données initiales
INSERT INTO plans (name, quota_monthly, rate_limit_per_minute, price_monthly) VALUES
('Free', 100, 10, 0.00),
('Starter', 1000, 30, 29.00),
('Pro', 10000, 100, 99.00);
```

### Table `usage_stats`
```sql
CREATE TABLE usage_stats (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    api_key_id UUID REFERENCES api_keys(id) ON DELETE SET NULL,
    endpoint VARCHAR(255),
    method VARCHAR(10),
    status_code INTEGER,
    processing_time_ms INTEGER,
    file_size_bytes INTEGER,
    timestamp TIMESTAMP DEFAULT NOW(),
    ip_address INET
);

-- Index pour requêtes fréquentes
CREATE INDEX idx_usage_user_timestamp ON usage_stats(user_id, timestamp DESC);
CREATE INDEX idx_usage_timestamp ON usage_stats(timestamp DESC);
```

---

## 🔐 Flux d'Authentification Proposé

### 1. Inscription Utilisateur
```
User → Frontend: Formulaire inscription (email, password)
Frontend → Backend: POST /api/auth/register
Backend: Créer user + envoyer email de vérification
Backend → User: Email avec lien de vérification
User → Backend: Click lien → GET /api/auth/verify/{token}
Backend: Activer compte
```

### 2. Génération de Clé API
```
User → Frontend: Login
Frontend → Backend: POST /api/auth/login → JWT token
User → Dashboard: "Generate API Key"
Frontend → Backend: POST /api/keys/generate (avec JWT)
Backend:
  1. Vérifier plan et quotas
  2. Générer clé: sk_live_{random_32_chars}
  3. Hasher et stocker
  4. Retourner clé EN CLAIR (1 seule fois!)
Frontend: Afficher clé avec warning "Copiez maintenant!"
```

### 3. Utilisation de la Clé
```
Client → API Conversion: POST /api/v1/convert + X-API-Key
API:
  1. Hasher la clé reçue
  2. Chercher dans DB (api_keys.key_hash)
  3. Vérifier user actif + plan valide
  4. Vérifier quotas (usage_stats du mois)
  5. Logger l'utilisation
  6. Exécuter conversion
```

---

## 🎨 Interface Utilisateur (Dashboard)

### Pages Principales

#### 1. Page de Login/Inscription
- Login avec email/password ou OAuth (Google, GitHub)
- Lien "Forgot password"
- Design moderne avec Tailwind CSS

#### 2. Dashboard Principal
```
┌─────────────────────────────────────────────────┐
│  👤 John Doe                    Plan: Starter   │
├─────────────────────────────────────────────────┤
│  📊 Usage ce mois: 127 / 1,000 conversions     │
│  ▓▓▓▓▓░░░░░ 12.7%                              │
├─────────────────────────────────────────────────┤
│  🔑 Vos Clés API                                │
│  ┌───────────────────────────────────────────┐ │
│  │ Production Key          🟢 Active          │ │
│  │ sk_live_Ab***************Xyz              │ │
│  │ Créée: 2025-10-15 | Dernière use: il y a 2h│
│  │ [Révoquer] [Réinitialiser]                │ │
│  └───────────────────────────────────────────┘ │
│  [+ Générer nouvelle clé]                      │
├─────────────────────────────────────────────────┤
│  📈 Statistiques (graphiques)                  │
│  - Conversions par jour (7 derniers jours)    │
│  - Temps de réponse moyen                     │
│  - Endpoints les plus utilisés                │
└─────────────────────────────────────────────────┘
```

#### 3. Page Billing (si facturation)
- Historique des paiements
- Upgrade/downgrade de plan
- Méthodes de paiement (Stripe)

#### 4. Page Documentation
- Guide "Getting Started"
- Exemples de code (Python, JavaScript, cURL)
- Référence API complète (Swagger embeddé)

---

## 💰 Modèles de Monétisation

### Option 1: Freemium avec Quotas
```
┌──────────────────────────────────────────────────┐
│  Plan        Quota/mois  Rate Limit  Prix/mois  │
├──────────────────────────────────────────────────┤
│  Free            100       10/min       €0      │
│  Starter       1,000       30/min      €29      │
│  Pro          10,000      100/min      €99      │
│  Enterprise   Custom     Custom     Sur devis   │
└──────────────────────────────────────────────────┘
```

### Option 2: Pay-as-you-go
- €0.05 par conversion (jusqu'à 1,000)
- €0.03 par conversion (1,001-10,000)
- €0.01 par conversion (10,001+)
- Facturation mensuelle

### Option 3: Hybrid
- Base gratuite: 100 conversions/mois
- Surplus: €0.10 par conversion supplémentaire
- Plans premium avec tarifs dégressifs

---

## 🔧 Modifications à Apporter à l'API Actuelle

### 1. Middleware de Validation Étendu

**Fichier**: `src/api/core/security.py`

```python
async def verify_api_key_with_quota(
    api_key: Optional[str] = Security(API_KEY_HEADER)
) -> dict:
    """
    Vérifie la clé API ET les quotas de l'utilisateur

    Returns:
        dict: {
            "user_id": UUID,
            "plan": str,
            "remaining_quota": int
        }
    """
    if not api_key:
        raise HTTPException(status_code=401, detail="API key manquante")

    # 1. Chercher la clé dans la DB
    key_record = await db.api_keys.find_one({
        "key_hash": hash_api_key(api_key),
        "is_active": True,
        "expires_at": {"$gt": datetime.now()}
    })

    if not key_record:
        raise HTTPException(status_code=401, detail="API key invalide")

    # 2. Charger l'utilisateur et son plan
    user = await db.users.find_one({"id": key_record["user_id"]})
    plan = await db.plans.find_one({"id": user["plan_id"]})

    # 3. Vérifier les quotas
    current_month = datetime.now().replace(day=1, hour=0, minute=0)
    usage_count = await db.usage_stats.count_documents({
        "user_id": user["id"],
        "timestamp": {"$gte": current_month}
    })

    if usage_count >= plan["quota_monthly"]:
        raise HTTPException(
            status_code=429,
            detail=f"Quota mensuel dépassé ({plan['quota_monthly']} conversions)"
        )

    # 4. Mettre à jour last_used_at
    await db.api_keys.update_one(
        {"id": key_record["id"]},
        {"$set": {"last_used_at": datetime.now()}}
    )

    return {
        "user_id": user["id"],
        "plan": plan["name"],
        "remaining_quota": plan["quota_monthly"] - usage_count
    }
```

### 2. Logging d'Utilisation

**Nouveau fichier**: `src/api/core/usage_tracking.py`

```python
async def log_api_usage(
    user_id: UUID,
    endpoint: str,
    method: str,
    status_code: int,
    processing_time_ms: int,
    file_size_bytes: int = 0,
    ip_address: str = None
):
    """Log l'utilisation pour facturation et analytics"""
    await db.usage_stats.insert_one({
        "user_id": user_id,
        "endpoint": endpoint,
        "method": method,
        "status_code": status_code,
        "processing_time_ms": processing_time_ms,
        "file_size_bytes": file_size_bytes,
        "ip_address": ip_address,
        "timestamp": datetime.now()
    })
```

### 3. Endpoints de Gestion

**Nouveau fichier**: `src/api/routes/account.py`

```python
@router.post("/api/keys/generate")
async def generate_api_key(
    name: str,
    current_user: dict = Depends(get_current_user)
):
    """Génère une nouvelle clé API pour l'utilisateur"""
    # Vérifier limite de clés (ex: max 5 par user)
    key_count = await db.api_keys.count_documents({
        "user_id": current_user["id"],
        "is_active": True
    })

    if key_count >= 5:
        raise HTTPException(400, "Limite de clés atteinte (max 5)")

    # Générer clé unique
    raw_key = f"sk_live_{secrets.token_urlsafe(32)}"
    key_hash = hash_api_key(raw_key)

    # Stocker dans DB
    await db.api_keys.insert_one({
        "id": uuid4(),
        "user_id": current_user["id"],
        "key_prefix": raw_key[:15] + "...",
        "key_hash": key_hash,
        "name": name,
        "created_at": datetime.now(),
        "is_active": True
    })

    return {
        "key": raw_key,  # Retourné 1 seule fois!
        "warning": "Copiez cette clé maintenant, elle ne sera plus visible."
    }
```

---

## 📅 Plan de Déploiement par Phases

### Phase 1: MVP (2-3 semaines)
- ✅ Base de données PostgreSQL
- ✅ Authentification utilisateurs (email/password)
- ✅ Génération de clés API
- ✅ Dashboard simple (liste clés + usage)
- ✅ Intégration à l'API existante
- ✅ Quotas basiques (Free: 100/mois)

### Phase 2: Améliorations (1-2 semaines)
- ✅ OAuth (Google, GitHub)
- ✅ Plans payants (Stripe)
- ✅ Dashboard analytics avancés
- ✅ Gestion d'équipe (invitations)
- ✅ Webhooks pour notifications

### Phase 3: Entreprise (sur demande)
- ✅ SSO (SAML)
- ✅ Support prioritaire
- ✅ SLA garantis
- ✅ Déploiement on-premise
- ✅ API de gestion programmatique

---

## 🔗 Mise à Jour Swagger UI

Une fois la plateforme déployée, mettre à jour le message:

**Avant** (actuel):
```
"Pour obtenir une clé API, veuillez contacter l'administrateur du service."
```

**Après** (avec plateforme):
```python
description = (
    "Clé API pour l'authentification. "
    f"Pour obtenir une clé, inscrivez-vous gratuitement sur {PLATFORM_URL}. "
    "Plan gratuit: 100 conversions/mois incluses."
)
```

---

## 📞 Prochaines Actions Recommandées

### Court Terme (Maintenant)
1. ✅ Décider du modèle de monétisation
2. ✅ Choisir la stack technique (Option 1, 2 ou 3)
3. ✅ Créer un mockup de dashboard
4. ✅ Évaluer le budget (hébergement + services tiers)

### Moyen Terme (Développement)
1. Setup infrastructure (DB, auth service)
2. Développer backend API de gestion
3. Développer frontend dashboard
4. Intégrer à l'API de conversion existante
5. Tests end-to-end

### Long Terme (Lancement)
1. Beta testing avec premiers utilisateurs
2. Monitoring et analytics
3. Support client
4. Marketing et acquisition

---

## 💡 Alternatives Quick-Win

Si le développement complet est trop lourd initialement:

### Option A: Service Managé (RapidAPI)
- Publier l'API sur RapidAPI Marketplace
- Gestion auth + billing automatique
- Commission: 20% des revenus
- Setup: ~1 journée

### Option B: Notion Database + Zapier
- Base Notion pour gérer users + clés
- Formulaire Typeform pour inscriptions
- Zapier pour auto-génération de clés
- Email automatique avec la clé
- Setup: ~2 jours

### Option C: Auth0 + Simple Dashboard
- Auth0 pour authentification
- Page Next.js simple pour générer clés
- Pas de quotas automatiques (monitoring manuel)
- Setup: ~1 semaine

---

**Document vivant - À mettre à jour selon l'évolution des besoins**

Pour toute question, consultez la documentation ou contactez l'équipe technique.
