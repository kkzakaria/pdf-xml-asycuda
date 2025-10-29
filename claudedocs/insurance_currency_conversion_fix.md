# Correction: Conversion devise de l'assurance

## Date
2025-01-29

## Problème identifié

L'assurance de la section 21 "Assurance Attestée" du RFCV était traitée comme étant déjà en XOF, alors qu'elle est dans la **devise de la section 16** (USD, EUR, etc.).

### Comportement incorrect (avant)
```
Section 21: 67.32 (supposé être XOF)
→ Répartition: 67.32 XOF sur les articles
```

### Comportement correct (après)
```
Section 21: 67.32 USD
Section 17: Taux = 566.67
→ Conversion: 67.32 × 566.67 = 38,148.22 XOF
→ Répartition: 38,148.22 XOF sur les articles
```

## Modification apportée

### Fichier: `src/rfcv_parser.py`
**Lignes 565-593**: Correction de l'extraction et conversion de l'assurance

#### Avant
```python
# Section 21: Assurance Attestée (insurance) - toujours en XOF
assurance_str = self._extract_field(r'21\.\s*Assurance Attestée.*?\n.*?\n([\d\s]+,\d{2})\s+[\d\s]+,\d{2}')

if assurance_str:
    assurance_value = self._parse_number(assurance_str)
    if assurance_value is not None:
        valuation.insurance = CurrencyAmount(
            amount_national=assurance_value,
            amount_foreign=None,  # ❌ Pas de montant étranger
            currency_code='XOF',
            currency_name='Franc CFA',
            currency_rate=1.0
        )
```

#### Après
```python
# Section 21: Assurance Attestée (insurance)
# IMPORTANT: L'assurance est dans la devise de la section 16 (USD, EUR, etc.)
# Il faut la convertir en XOF en multipliant par le taux de change (section 17)
assurance_str = self._extract_field(r'21\.\s*Assurance Attestée.*?\n.*?\n([\d\s]+,\d{2})\s+[\d\s]+,\d{2}')

if assurance_str and currency and currency_rate:
    # Assurance en devise étrangère (section 16)
    assurance_foreign = self._parse_number(assurance_str)
    rate_value = self._parse_number(currency_rate)

    if assurance_foreign is not None and rate_value is not None:
        # Convertir en XOF: assurance_devise × taux_change
        assurance_xof = assurance_foreign * rate_value

        valuation.insurance = CurrencyAmount(
            amount_national=assurance_xof,
            amount_foreign=assurance_xof,  # ✅ XOF: amount_national = amount_foreign
            currency_code='XOF',
            currency_name='Franc CFA',
            currency_rate=1.0
        )
```

## Tests ajoutés

### Fichier: `tests/test_insurance_conversion.py`
5 tests d'intégration validant:
1. Conversion correcte pour RFCV 03286 (3 articles)
2. Conversion correcte pour RFCV 03475 (35 motos)
3. Conversion correcte pour RFCV 03977 (1 article poudre)
4. Format XOF assurance globale (`amount_national` = `amount_foreign`)
5. Format XOF assurance par article (`amount_national` = `amount_foreign`)

```bash
pytest tests/test_insurance_conversion.py -v
# ✅ 5 passed
```

## Validation

### Test 1: RFCV 03286
```
Section 21: 67.32 USD
Taux: 566.67
Conversion: 67.32 × 566.67 = 38,148.22 XOF ✅
Répartition: 398 + 32,373 + 5,377 = 38,148 XOF ✅
```

### Test 2: RFCV 03475 (35 motos)
```
Section 21: 44.05 USD
Taux: 567.27
Conversion: 44.05 × 567.27 = 24,988.24 XOF ✅
Répartition: 35 articles × ~714 XOF = 24,988 XOF ✅
```

### Test 3: RFCV 03977 (poudre)
```
Section 21: 57.36 USD
Taux: 575.7807
Conversion: 57.36 × 575.7807 = 33,026.78 XOF ✅
Répartition: 1 article = 33,027 XOF ✅ (±1 arrondi)
```

## Impact

### Calculs affectés
- ✅ Assurance globale (valuation.insurance)
- ✅ Assurance par article (item.valuation_item.insurance)
- ✅ Répartition proportionnelle selon FOB

### Calculs non affectés
- ✅ FOB (déjà en devise étrangère)
- ✅ FRET (déjà en devise étrangère)
- ✅ Poids (toujours en KG)

### Format XML ASYCUDA
- ✅ `Amount_national_currency`: Montant en XOF
- ✅ `Amount_foreign_currency`: Montant en XOF (égal à amount_national pour XOF)
- ✅ `Currency_code`: "XOF"
- ✅ `Currency_rate`: 1.0

## Régression

Tous les tests existants passent:
```bash
pytest tests/test_proportional_calculator.py -v
# ✅ 16 passed

pytest tests/test_insurance_conversion.py -v
# ✅ 5 passed
```

## Références

- Section RFCV 16: Code Devise (USD, EUR, etc.)
- Section RFCV 17: Taux de Change
- Section RFCV 21: Assurance Attestée (en devise section 16)
- Format ASYCUDA: XOF avec `amount_national` = `amount_foreign`
- Méthode du reste le plus grand: Garantit somme exacte après conversion

## Conclusion

La correction garantit que:
1. ✅ L'assurance est correctement convertie de la devise étrangère en XOF
2. ✅ La répartition proportionnelle utilise la valeur convertie
3. ✅ Le format XML ASYCUDA est respecté (XOF avec montants égaux)
4. ✅ La méthode du reste le plus grand garantit la cohérence des totaux
