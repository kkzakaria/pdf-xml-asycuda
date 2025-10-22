# Analyse Numéro de Châssis/Série - Traitement Spécial

## Comparaison DKS5477 vs IM18215

### DKS5477 (Poudre de Carbone)

**Type de marchandise**: RESIN RUBBER POWDER (Poudre de résine)  
**Code SH**: 28030000 (Carbone noir)

#### Attached_documents (7 documents)
```
0007: FACTURE
0014: JUSTIFICATION D'ASSURANCE
6603: BORDEREAU DE SUIVI DE CARGAISON
2500: NUMERO DE LIGNE ARTICLE
2501: RFCV
2050: ATTESTATION D'IMPORTATION
6610: FDI
```

**❌ PAS de code 6122 (CHASSIS)**

#### Free_text_1
```xml
<Free_text_1>2025/BC/SN18717 DU 23/08/2025</Free_text_1>
```
**Contenu**: Référence facture + date (PAS de numéro de châssis)

#### Marks2_of_packages
```xml
<Marks2_of_packages>
  <null/>
</Marks2_of_packages>
```
**Vide** (pas de numéro de série)

---

### IM18215 (Motos)

**Type de marchandise**: MOTORCYCLE FH125-3 LRFPCJLD1S0F18969  
**Code SH**: 87112091 (Motocycles)

#### Attached_documents (8 documents)
```
0007: FACTURE
0014: JUSTIFICATION D'ASSURANCE
6603: BORDEREAU DE SUIVI DE CARGAISON
6122: CHASSIS MOTOS (LRFPCJLDIS0F18969) ⭐ SPÉCIAL
2500: NUMERO DE LIGNE ARTICLE
2501: RFCV
6610: FDI
2050: ATTESTATION D'IMPORTATION
```

**✅ Code 6122 présent** avec numéro de châssis

#### Free_text_1
```xml
<Free_text_1>CH: LRFPCJLDIS0F18969</Free_text_1>
```
**Contenu**: Numéro de châssis avec préfixe "CH:"

#### Marks2_of_packages
```xml
<Marks2_of_packages>CH: LRFPCJLDIS0F18969</Marks2_of_packages>
```
**Contenu**: Numéro de châssis avec préfixe "CH:"

---

## Conclusion

### ✅ Tu as raison !

Le traitement du **numéro de châssis/série** est effectivement **spécifique à certains types de marchandises**.

### Règles Identifiées

| Marchandise | Code Document 6122 | Free_text_1 | Marks2_of_packages |
|-------------|-------------------|-------------|-------------------|
| **Véhicules** (motos, tricycles, voitures) | ✅ OUI | "CH: {numero}" | "CH: {numero}" |
| **Autres** (poudre, sacs, etc.) | ❌ NON | Facture + Date | Vide |

### Codes SH Concernés (Probablement)

Les marchandises avec numéro de châssis/série sont généralement :

- **8711**: Motocycles et cyclomoteurs
- **8704**: Véhicules automobiles pour le transport de marchandises (tricycles)
- **8703**: Voitures de tourisme et autres véhicules
- **8702**: Véhicules automobiles pour le transport de personnes

**Logique**: Tout code SH commençant par **87** (Véhicules et matériel de transport terrestre)

### Extraction Numéro Châssis

**Dans la description PDF**: "MOTORCYCLE FH125-3 **LRFPCJLD1S0F18969**"

**Pattern VIN**: Numéro d'identification véhicule = 17 caractères alphanumériques
- Format international standard
- Exemple: `LRFPCJLD1S0F18969`

### Recommandation Révisée

#### 🔴 Priorité Haute

1. **Extraire type de colisage** (section 24) - TOUS les cas
   - Pattern: `(\d+)\s+(CARTONS|PACKAGES|etc\.)`
   - Mapping: CARTONS→CT, PACKAGES→PK

2. **Ajouter Previous_document_reference** - TOUS les cas
   - Format: "{invoice_number} DU {invoice_date}"
   - Utiliser dans Previous_doc

#### 🟡 Priorité Conditionnelle (Véhicules uniquement)

3. **Extraire numéro de châssis** - SI code SH commence par 87
   - Pattern: `([A-Z0-9]{17})` dans la description
   - Ajouter Attached_document code 6122
   - Remplir Free_text_1: "CH: {numero}"
   - Remplir Marks2_of_packages: "CH: {numero}"

### Code SH à Vérifier

```python
def has_chassis_number(hs_code: str) -> bool:
    """Détermine si la marchandise a un numéro de châssis"""
    # Code SH commence par 87 = Véhicules
    return hs_code.startswith('87')
```

### Impact sur Notre Code

**Actuellement**:
- Free_text_1: Vide
- Marks2_of_packages: Vide
- Attached_documents: 3 documents (FACTURE, RFCV, FDI)

**Après amélioration**:

**Pour TOUS les produits**:
- Previous_document_reference: "{invoice} DU {date}"
- Kind_of_packages_code: Extrait de section 24

**Pour véhicules SEULEMENT** (HS code 87xx):
- Attached_document code 6122: Numéro châssis
- Free_text_1: "CH: {numero}"
- Marks2_of_packages: "CH: {numero}"

## Tests à Faire

1. **DOSSIER 18237.pdf** - Tricycles (8704.31.19.90)
   - Vérifier si descriptions contiennent numéros VIN
   - Tester extraction châssis

2. **BL_2025_03228_RFCV.pdf** - Sacs à main (4202.22.90.00)
   - Confirmer absence numéro châssis
   - Free_text_1 devrait avoir facture + date

3. **Nouveaux fichiers** - Motos (IM18215)
   - Implémenter extraction VIN
   - Générer code 6122

