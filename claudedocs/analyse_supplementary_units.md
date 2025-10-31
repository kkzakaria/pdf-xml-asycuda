# Analyse - Supplementary Units (Unités Supplémentaires)

**Date**: 2025-10-31

## 📋 Structure Complète

### 1️⃣ Modèle de Données (`models.py:181-185`)

```python
@dataclass
class SupplementaryUnit:
    """Unité supplémentaire"""
    code: Optional[str] = None        # Code de l'unité (ex: 'QA', '40')
    name: Optional[str] = None        # Nom de l'unité (ex: "Unité d'apurement", "NOMBRE")
    quantity: Optional[float] = None  # Quantité dans cette unité
```

**Utilisation** dans `Tarification` (ligne 194):
```python
supplementary_units: List[SupplementaryUnit] = field(default_factory=list)
```

### 2️⃣ Extraction RFCV (`rfcv_parser.py:763-768`)

**Code actuel** : L'unité d'appurement est **codée en dur**

```python
supplementary_units=[
    SupplementaryUnit(
        code='QA',
        name='Unité d\'apurement',
        quantity=quantity  # Quantité extraite de section 26
    )
]
```

**Source de la quantité** :
- Section "26. Articles" du RFCV
- Colonne "Quantité attestée"
- Même quantité que `item.packages[0].number_of_packages`

### 3️⃣ Génération XML (`xml_generator.py:598-609`)

**Structure XML** : 3 blocs `Supplementary_unit` (standard ASYCUDA)

```xml
<!-- Bloc 1: Unité d'apurement (rempli) -->
<Supplementary_unit>
  <Suppplementary_unit_code>QA</Suppplementary_unit_code>
  <Suppplementary_unit_name>Unité d'apurement</Suppplementary_unit_name>
  <Suppplementary_unit_quantity>1.0</Suppplementary_unit_quantity>
</Supplementary_unit>

<!-- Bloc 2: Vide -->
<Supplementary_unit>
  <Suppplementary_unit_code><null/></Suppplementary_unit_code>
  <Suppplementary_unit_name/>
  <Suppplementary_unit_quantity/>
</Supplementary_unit>

<!-- Bloc 3: Vide -->
<Supplementary_unit>
  <Suppplementary_unit_code><null/></Suppplementary_unit_code>
  <Suppplementary_unit_name/>
  <Suppplementary_unit_quantity/>
</Supplementary_unit>
```

**Note** : La faute de frappe "Suppplementary" (3 p) est **intentionnelle** et conforme au standard ASYCUDA.

## 🔍 Analyse du Système Actuel

### Codes d'Unités Supplémentaires Standards

| Code | Nom | Usage |
|------|-----|-------|
| **QA** | Unité d'apurement | Unité de dédouanement (système automatique) |
| **40** | NOMBRE | Quantité en nombre d'articles |
| **KG** | Kilogramme | Poids en kg |
| **L** | Litre | Volume en litres |

**Source** : Tarif douanier ASYCUDA, pas le RFCV

### Où Trouver l'Information

❌ **PAS dans le RFCV** : Le document RFCV ne contient pas d'informations sur les unités supplémentaires

✅ **Source réelle** : Les unités supplémentaires sont spécifiées dans le tarif douanier CEDEAO/UEMOA pour chaque code HS

📝 **Documentation** : `claudedocs/VERIFICATION_SECTION_26_ARTICLES.md` (ligne 118-132)

### Comportement Actuel

**Système en place** :
1. ✅ Génère automatiquement une unité "QA" (Unité d'apurement)
2. ✅ Utilise la quantité extraite de la section 26
3. ✅ Remplit 3 blocs (standard ASYCUDA) : 1 rempli + 2 vides

**Rationale** :
- Le code 'QA' est utilisé par défaut dans ASYCUDA Côte d'Ivoire
- La quantité provient de la "Quantité attestée" du RFCV
- Les 2 blocs vides permettent la saisie manuelle lors du dédouanement

## 📄 Exemple Réel

### RFCV Source : Section 26 Articles

```
Tableau des articles:
...
Quantité attestée: 1
```

### XML Généré

```xml
<Tarification>
  <HSCode>
    <Commodity_code>87112090</Commodity_code>
    <Precision_1>00</Precision_1>
  </HSCode>
  <Extended_procedure>4000</Extended_procedure>
  <National_procedure>000</National_procedure>

  <!-- 3 blocs Supplementary_unit -->
  <Supplementary_unit>
    <Suppplementary_unit_code>QA</Suppplementary_unit_code>
    <Suppplementary_unit_name>Unité d'apurement</Suppplementary_unit_name>
    <Suppplementary_unit_quantity>1.0</Suppplementary_unit_quantity>
  </Supplementary_unit>
  <Supplementary_unit>
    <Suppplementary_unit_code><null/></Suppplementary_unit_code>
    <Suppplementary_unit_name/>
    <Suppplementary_unit_quantity/>
  </Supplementary_unit>
  <Supplementary_unit>
    <Suppplementary_unit_code><null/></Suppplementary_unit_code>
    <Suppplementary_unit_name/>
    <Suppplementary_unit_quantity/>
  </Supplementary_unit>

  <Item_price>532.0</Item_price>
</Tarification>
```

## 🎯 Options de Modification

### Option 1: Laisser tel quel (Actuel)

**Avantages** :
- ✅ Code 'QA' est standard ASYCUDA Côte d'Ivoire
- ✅ Quantité correctement extraite du RFCV
- ✅ Blocs vides permettent la saisie manuelle

**Inconvénients** :
- ⚠️ Code/nom générique, pas spécifique au code HS
- ⚠️ Peut ne pas correspondre au tarif douanier réel

### Option 2: Tout mettre à null

**Avantages** :
- ✅ Cohérent avec autres champs non disponibles dans RFCV
- ✅ Force la saisie manuelle du bon code lors du dédouanement
- ✅ Évite les erreurs dues à un code générique

**Inconvénients** :
- ❌ Perd l'information de quantité pourtant disponible
- ❌ Demande plus de travail lors de la saisie

### Option 3: Conserver quantité, code/nom à null

**Structure proposée** :
```xml
<Supplementary_unit>
  <Suppplementary_unit_code><null/></Suppplementary_unit_code>
  <Suppplementary_unit_name/>
  <Suppplementary_unit_quantity>1.0</Suppplementary_unit_quantity>
</Supplementary_unit>
```

**Avantages** :
- ✅ Conserve la quantité attestée du RFCV
- ✅ Code/nom null = force vérification du tarif douanier
- ✅ Compromis entre automatisation et exactitude

## 🔄 Impact sur le Regroupement d'Articles

Le système de regroupement (`src/item_grouper.py`) gère les quantités dans `supplementary_units`:

**Ligne 207-227** : Fonction `_set_supplementary_unit_quantity`
```python
# Crée ou met à jour supplementary_units[0].quantity
if not item.tarification.supplementary_units:
    item.tarification.supplementary_units = [
        SupplementaryUnit(
            code='QA',
            name='Unité d\'apurement',
            quantity=quantity
        )
    ]
else:
    item.tarification.supplementary_units[0].quantity = quantity
```

**Lors du regroupement** :
- Premier article du premier groupe : `quantity = total_packages`
- Autres articles : `quantity = 0`

## 📊 Conformité ASYCUDA

### Standard ASYCUDA

**Structure** : 3 blocs Supplementary_unit par article

**Champs** :
- `Suppplementary_unit_code` : Code de l'unité (tarif douanier)
- `Suppplementary_unit_name` : Nom de l'unité
- `Suppplementary_unit_quantity` : Quantité dans cette unité

**Validation** : ✅ Notre structure est conforme

### Pratique Côte d'Ivoire

**Observation** (d'après `claudedocs/COMPARAISON_ASYCUDA_IM18215_RFCV.md`) :

Les déclarations ASYCUDA réelles utilisent :
- Code QA : Unité d'apurement (automatique)
- Code 40 : NOMBRE (quantité physique)

**Conclusion** : Le code 'QA' est approprié pour la première unité

## 📚 Références Techniques

### Fichiers Impactés

| Fichier | Lignes | Fonction |
|---------|--------|----------|
| `src/models.py` | 181-185, 194 | Définition SupplementaryUnit |
| `src/rfcv_parser.py` | 763-768 | Création avec code 'QA' |
| `src/xml_generator.py` | 598-609 | Génération 3 blocs XML |
| `src/item_grouper.py` | 207-227 | Mise à jour quantité |

### Tests Existants

**Tests de regroupement** (`tests/test_item_grouping.py`) :
- 9 tests vérifient le comportement des `supplementary_units`
- Tous les tests vérifient que `supplementary_units[0].quantity` est correctement assigné
- ✅ 9/9 tests passent

**Tests de conversion** :
- 39 tests de non-régression
- ✅ 39/39 tests passent

## 🎯 Recommandation

### Option Recommandée : **Option 3** (Quantité conservée, code/nom à null)

**Justification** :
1. **Cohérence** : Align avec la philosophie de mettre à null les champs non disponibles dans RFCV
2. **Exactitude** : Force la vérification du bon code d'unité selon le tarif douanier
3. **Information préservée** : Conserve la quantité attestée du RFCV
4. **Pratique** : Facilite la saisie (quantité déjà remplie, juste besoin d'ajouter le code)

### Modifications Requises

**1. rfcv_parser.py** (ligne 763-768) :
```python
# AVANT
supplementary_units=[
    SupplementaryUnit(
        code='QA',
        name='Unité d\'apurement',
        quantity=quantity
    )
]

# APRÈS
supplementary_units=[
    SupplementaryUnit(
        code=None,
        name=None,
        quantity=quantity
    )
]
```

**2. item_grouper.py** (ligne 218-226) :
```python
# AVANT
item.tarification.supplementary_units = [
    SupplementaryUnit(
        code='QA',
        name='Unité d\'apurement',
        quantity=quantity
    )
]

# APRÈS
item.tarification.supplementary_units = [
    SupplementaryUnit(
        code=None,
        name=None,
        quantity=quantity
    )
]
```

**3. xml_generator.py** : Aucune modification nécessaire
- Les champs null sont déjà gérés par `self._add_simple_element`

### Alternative : Tout mettre à null (Option 2)

Si l'utilisateur préfère **tout mettre à null** :

**Modifications** :
- `rfcv_parser.py` : `supplementary_units=[]` (liste vide)
- `xml_generator.py` : Garder la génération des 3 blocs vides
- `item_grouper.py` : Ne pas créer de SupplementaryUnit

**Impact** : 3 blocs Supplementary_unit complètement vides dans le XML

## ✅ Validation Nécessaire

Après modification, vérifier :
- [ ] Les 3 blocs Supplementary_unit sont générés
- [ ] Les champs null utilisent `<null/>` ou sont vides selon le cas
- [ ] Les 39 tests de non-régression passent
- [ ] Les 9 tests de regroupement fonctionnent correctement
- [ ] Le XML reste conforme au standard ASYCUDA
