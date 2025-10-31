# Rapport de Validation - Numéro de Facture sur Premier Article

**Date**: 2025-10-31
**Modification**: Le numéro de facture apparaît uniquement sur le premier article

## 🎯 Objectif

Corriger la propagation du numéro de facture pour qu'il apparaisse **uniquement sur le premier article** au lieu de tous les articles.

## ✅ Modifications Effectuées

### 1. `rfcv_parser.py` - Ligne 82-94

**Avant** : Ajout de `Previous_document_reference` à tous les articles
```python
for item in rfcv_data.items:
    item.previous_document_reference = prev_doc_ref
```

**Après** : Ajout uniquement au premier article
```python
# Ajouter uniquement au premier article
rfcv_data.items[0].previous_document_reference = prev_doc_ref
```

### 2. `rfcv_parser.py` - Ligne 936-984

**Avant** : Document FACTURE (code 0007) ajouté dans la boucle pour tous les articles

**Après** : Document FACTURE ajouté avant la boucle, uniquement au premier article
```python
# Ajouter la FACTURE au premier article uniquement
if invoice_number and rfcv_data.items:
    rfcv_data.items[0].attached_documents.append(AttachedDocument(
        code='0007',
        name='FACTURE',
        reference=invoice_number,
        from_rule=1,
        document_date=invoice_date
    ))

# Ajouter les autres documents à tous les items
for item in rfcv_data.items:
    # Document 2: RFCV (code 2501) - TOUS LES ARTICLES
    # Document 3: FDI (code 6610) - TOUS LES ARTICLES
```

## 🧪 Tests Unitaires - 7/7 PASSÉS

```bash
$ python -m pytest tests/test_invoice_number.py -v

✅ test_invoice_number_first_item_only_attached_documents PASSED
✅ test_rfcv_and_fdi_on_all_items PASSED
✅ test_previous_document_reference_first_item_only PASSED
✅ test_invoice_number_with_single_item PASSED
✅ test_invoice_number_with_empty_items PASSED
✅ test_invoice_number_after_grouping PASSED
✅ test_count_invoice_documents_multiple_items PASSED

7 passed in 0.54s
```

### Couverture des Tests

| Test | Description | Résultat |
|------|-------------|----------|
| `test_invoice_number_first_item_only_attached_documents` | Document FACTURE (0007) uniquement sur premier article | ✅ PASS |
| `test_rfcv_and_fdi_on_all_items` | Documents RFCV (2501) et FDI (6610) sur tous les articles | ✅ PASS |
| `test_previous_document_reference_first_item_only` | Previous_document_reference uniquement sur premier article | ✅ PASS |
| `test_invoice_number_with_single_item` | Fonctionnement avec 1 seul article | ✅ PASS |
| `test_invoice_number_with_empty_items` | Gestion des listes vides sans crash | ✅ PASS |
| `test_invoice_number_after_grouping` | Facture sur premier article après regroupement | ✅ PASS |
| `test_count_invoice_documents_multiple_items` | Exactement 1 document FACTURE au total (10 articles) | ✅ PASS |

## 📄 Test avec RFCV Réel

### Fichier: `tests/BL_2025_02830_RFCV.pdf`

**Extraction**:
- Importateur: GLOBAL BETY NEGOCE
- Exportateur: KOLOKELH TRADING FZE
- Nombre d'articles: 2
- Numéro facture: 2025/GB/SN17705
- Date facture: 10/06/2025

### Résultat XML

#### Premier Article (Article 1)
```xml
<Item>
  <Attached_documents>
    <Attached_document_code>0007</Attached_document_code>
    <Attached_document_name>FACTURE</Attached_document_name>
    <Attached_document_reference>2025/GB/SN17705</Attached_document_reference>
    <Attached_document_from_rule>1</Attached_document_from_rule>
    <Attached_document_date>6/10/25</Attached_document_date>
  </Attached_documents>
  <Attached_documents>
    <Attached_document_code>2501</Attached_document_code>
    <!-- RFCV -->
  </Attached_documents>
  <Attached_documents>
    <Attached_document_code>6610</Attached_document_code>
    <!-- FDI -->
  </Attached_documents>
  <Previous_doc>
    <Previous_document_reference>2025/GB/SN17705 DU 10/06/2025</Previous_document_reference>
  </Previous_doc>
</Item>
```

#### Deuxième Article (Article 2)
```xml
<Item>
  <!-- ❌ PAS de document FACTURE (0007) -->
  <Attached_documents>
    <Attached_document_code>2501</Attached_document_code>
    <!-- ✅ RFCV présent -->
  </Attached_documents>
  <Attached_documents>
    <Attached_document_code>6610</Attached_document_code>
    <!-- ✅ FDI présent -->
  </Attached_documents>
  <Previous_doc>
    <Previous_document_reference/>
    <!-- ❌ Vide -->
  </Previous_doc>
</Item>
```

### Comptage XML

```bash
$ grep -c 'Attached_document_code>0007' output/test_invoice.xml
1   # ✅ Exactement 1 document FACTURE

$ grep -c 'Attached_document_code>2501' output/test_invoice.xml
2   # ✅ Document RFCV sur les 2 articles

$ grep -c 'Attached_document_code>6610' output/test_invoice.xml
2   # ✅ Document FDI sur les 2 articles
```

## 🔄 Tests de Non-Régression

### Tests Détection Châssis - 22/22 PASSÉS
```bash
$ python -m pytest tests/test_chassis_detection.py -v
✅ 22 passed in 0.28s
```

### Tests Regroupement Articles - 10/10 PASSÉS
```bash
$ python -m pytest tests/test_item_grouping.py -v
✅ 10 passed in 0.03s
```

### Tests API - 26/26 PASSÉS
```bash
$ python -m pytest tests/api/ -v
✅ 26 passed in 23.54s
```

## 📊 Résumé Validation

| Catégorie | Tests | Résultat |
|-----------|-------|----------|
| Numéro de facture | 7 | ✅ 7/7 PASS |
| Détection châssis | 22 | ✅ 22/22 PASS |
| Regroupement articles | 10 | ✅ 10/10 PASS |
| API | 26 | ✅ 26/26 PASS |
| **TOTAL** | **65** | ✅ **65/65 PASS** |

## ✅ Validation Finale

**Comportement Attendu** ✅ CONFORME

- **Document FACTURE (code 0007)** : Apparaît **uniquement** sur le premier article
- **Previous_document_reference** : Rempli **uniquement** sur le premier article
- **Document RFCV (code 2501)** : Apparaît sur **tous** les articles
- **Document FDI (code 6610)** : Apparaît sur **tous** les articles
- **Compatibilité regroupement** : Le premier article après regroupement reçoit bien le document FACTURE
- **Gestion cas limites** : Fonctionne avec 1 seul article et liste vide

## 🎯 Conformité ASYCUDA

Le comportement est maintenant **conforme aux standards douaniers** :
- Une seule facture commerciale référence tous les articles de la déclaration
- Le numéro de facture apparaît sur le premier article uniquement
- Les documents de vérification (RFCV, FDI) sont présents sur tous les articles pour traçabilité

## 📝 Recommandations

✅ **Déploiement recommandé** - Tous les tests passent sans régression

Validation effectuée sur :
- Python 3.13.5
- pytest 8.4.2
- 65 tests unitaires et d'intégration
