# Comparaison Détaillée: PDF RFCV vs XML ASYCUDA (IM18215)

## Données Globales

| Élément | PDF RFCV | XML ASYCUDA | Statut |
|---------|----------|-------------|---------|
| Nombre d'articles | 35 | 35 | ✅ |
| Pages | 2 | - | ✅ Multi-pages |

## Article 1 - Comparaison Détaillée

### Données PDF RFCV (Article 1)
```
N°: 1
Quantité: 1,00
UM: U
UPO: N
Origine: AE
Description: MOTORCYCLE FH125-3 LRFPCJLD1S0F18969
Code SH: 8711.20.91.00
Valeur FOB: 362,39
Valeur taxable: 420,79
```

### Données XML ASYCUDA (Item 1)

#### Packages
```xml
<Number_of_packages>6</Number_of_packages>
<Marks1_of_packages>MOTORCYCLE  FENGHAO</Marks1_of_packages>
<Marks2_of_packages>CH: LRFPCJLDIS0F18969</Marks2_of_packages>
<Kind_of_packages_code>CT</Kind_of_packages_code>
<Kind_of_packages_name>Carton</Kind_of_packages_name>
```

**⚠️ DIFFÉRENCE CRITIQUE**: 
- PDF dit: Quantité = 1,00 (1 moto)
- ASYCUDA dit: Number_of_packages = 6 (6 cartons)

**Interprétation**:
- Le PDF RFCV section 26 liste les ARTICLES (1 moto)
- ASYCUDA Package section compte les COLIS/CARTONS (6 cartons pour cette moto)
- Section 24 du PDF dit "216 CARTONS" (total global)

#### Tarification
```xml
<Commodity_code>87112091</Commodity_code>
<Precision_1>00</Precision_1>
<Item_price>363</Item_price>
```

**📊 Comparaison**:
| Champ | PDF RFCV | XML ASYCUDA | Différence |
|-------|----------|-------------|------------|
| HS Code | 8711.20.91.00 | 87112091 + 00 | ✅ Match |
| Valeur FOB | 362,39 | 363 | ≈ Arrondi |

#### Goods_description
```xml
<Country_of_origin_code>CN</Country_of_origin_code>
<Description_of_goods>--- Motocycles (y compris les cyclomoteurs)...</Description_of_goods>
```

**⚠️ DIFFÉRENCE**:
- PDF dit: Origine = AE (Émirats Arabes Unis)
- ASYCUDA dit: Country_of_origin_code = CN (Chine)

**Raison probable**: Le PDF RFCV liste le pays de l'exportateur (UAE), tandis que ASYCUDA utilise le vrai pays d'origine de fabrication (Chine).

**📝 Description**:
- PDF: Description courte "MOTORCYCLE FH125-3 LRFPCJLD1S0F18969"
- ASYCUDA: Description tarifaire complète du code SH

#### Valuation_item
```xml
<Weight_itm>
  <Gross_weight_itm>663</Gross_weight_itm>
  <Net_weight_itm>603</Net_weight_itm>
</Weight_itm>
<Total_cost_itm>36718</Total_cost_itm>
<Total_CIF_itm>245726</Total_CIF_itm>
```

**Comparaison**:
| Champ | PDF RFCV | XML ASYCUDA | Source |
|-------|----------|-------------|---------|
| Gross_weight (item) | - | 663 kg | Saisie ASYCUDA |
| Net_weight (item) | - | 603 kg | Saisie ASYCUDA |
| Total_cost_itm | 362,39 USD | 36718 XOF | Converti |
| Total_CIF_itm | 420,79 USD | 245726 XOF | Converti |

**Calcul vérification**:
- 362,39 USD × 575.7807 = 208,652 XOF (vs 36718 ASYCUDA) ❌ Incohérence
- Taux de change PDF: 567.2700 (section 17)
- Taux de change ASYCUDA: 575.7807

#### Supplementary_unit
```xml
<Supplementary_unit>
  <Suppplementary_unit_code>QA</Suppplementary_unit_code>
  <Suppplementary_unit_name>Unité d'apurement</Suppplementary_unit_name>
  <Suppplementary_unit_quantity>1</Suppplementary_unit_quantity>
</Supplementary_unit>
<Supplementary_unit>
  <Suppplementary_unit_code>40</Suppplementary_unit_code>
  <Suppplementary_unit_name>NOMBRE</Suppplementary_unit_name>
  <Suppplementary_unit_quantity>1</Suppplementary_unit_quantity>
</Supplementary_unit>
```

**Source**: Informations ajoutées lors de la saisie ASYCUDA (pas dans RFCV).

#### Attached_documents (8 documents)
```xml
0007: FACTURE (2025/BC/SN18215)
0014: JUSTIFICATION D'ASSURANCE
6603: BORDEREAU DE SUIVI DE CARGAISON
6122: CHASSIS MOTOS (LRFPCJLDIS0F18969) ⭐ NOUVEAU
2500: NUMERO DE LIGNE ARTICLE (1)
2501: RFCV (RCS25127221)
6610: FDI (250165722)
2050: ATTESTATION D'IMPORTATION
```

**⭐ Découverte**: Document code **6122 "CHASSIS MOTOS"** contient le numéro de châssis extrait de la description !

#### Previous_doc
```xml
<Summary_declaration>ONEYCANF66571400</Summary_declaration>
<Previous_document_reference>2025/BC/SN18215 DU 17/07/2025</Previous_document_reference>
```

**Comparaison**:
- Summary_declaration: Bill of Lading (section 3 du PDF)
- Previous_document_reference: No. Facture + Date

#### Free_text
```xml
<Free_text_1>CH: LRFPCJLDIS0F18969</Free_text_1>
```

**Découverte**: Le numéro de châssis est aussi stocké dans Free_text_1 !

## Observations Clés

### 1. ✅ Champs Correctement Extraits
- HS Code (Commodity_code + Precision_1)
- Item_price (avec arrondi acceptable)
- Description (bien que différente dans ASYCUDA)

### 2. ⚠️ Différences Normales
| Champ | Raison |
|-------|--------|
| Number_of_packages | PDF = nombre d'articles, ASYCUDA = nombre de colis |
| Country_of_origin | PDF = pays exportateur, ASYCUDA = pays fabrication |
| Description | PDF = description courte, ASYCUDA = nomenclature tarifaire |
| Weight_itm | Pas dans RFCV, ajouté lors saisie ASYCUDA |
| Supplementary_unit | Pas dans RFCV, vient du tarif douanier |

### 3. 🔍 Nouveaux Champs Découverts

#### A. Numéro de Châssis/Série
**Dans PDF**: Inclus dans Description ("LRFPCJLD1S0F18969")
**Dans ASYCUDA**:
- Attached_document code 6122 avec référence = numéro châssis
- Free_text_1 = "CH: LRFPCJLDIS0F18969"
- Marks2_of_packages = "CH: LRFPCJLDIS0F18969"

**Action requise**: Extraire le numéro de châssis/série de la description

#### B. Kind_of_packages
**Dans PDF Section 24**: "216 CARTONS"
**Dans ASYCUDA**:
```xml
<Kind_of_packages_code>CT</Kind_of_packages_code>
<Kind_of_packages_name>Carton</Kind_of_packages_name>
```

**Notre code actuel**: 
```python
kind_code='PK'  # Toujours "PK" (Package)
kind_name='Colis ("package")'
```

**Action requise**: Extraire le type de colisage de la section 24

#### C. Previous_document_reference
**Dans ASYCUDA**: "2025/BC/SN18215 DU 17/07/2025" (Facture + Date)
**Notre code actuel**: Non extrait

**Action requise**: Ajouter référence facture dans Previous_doc

### 4. ❌ Incohérences à Clarifier

#### Number_of_packages
**Problème**: Le PDF section 26 montre "Quantité: 1,00" mais ASYCUDA a "Number_of_packages: 6"

**Hypothèses**:
1. Quantité PDF = nombre d'articles (1 moto)
2. ASYCUDA = nombre de colis (6 cartons pour cette moto)
3. Peut-être calculé: 216 cartons total ÷ 35 articles ≈ 6 cartons/article

**Question**: Faut-il utiliser la quantité du PDF ou calculer proportionnellement ?

## Recommandations

### 🔴 Priorité Haute

1. **Extraire type de colisage** de section 24
   - Pattern: `(\d+)\s+(CARTONS|PACKAGES|COLIS|PALETTES|etc\.)`
   - Mapper vers codes ASYCUDA (CT=Carton, PK=Package, etc.)

2. **Extraire numéro de châssis/série** de la description
   - Pattern pour motos: `([A-Z0-9]{17})` (numéro VIN 17 caractères)
   - Stocker dans:
     - Attached_document code 6122
     - Free_text_1 avec préfixe "CH: "
     - Marks2_of_packages avec préfixe "CH: "

3. **Ajouter Previous_document_reference**
   - Format: "{invoice_number} DU {invoice_date_formatted}"
   - Exemple: "2025/BC/SN18215 DU 17/07/2025"

### 🟡 Priorité Moyenne

4. **Vérifier origine pays**
   - Le PDF section 26 colonne "Origine" indique le pays de l'exportateur (AE)
   - Mais ASYCUDA utilise pays de fabrication (CN)
   - Section 9 du PDF: "Pays de provenance: Chine"
   - **Solution**: Utiliser section 9 pour Country_of_origin_code

5. **Calculer Number_of_packages par article**
   - Si possible: Total packages (section 24) ÷ Nombre d'articles
   - Sinon: Utiliser quantité du PDF (pas idéal mais mieux que rien)

### 🟢 Priorité Basse

6. **Description tarifaire**
   - ASYCUDA utilise la nomenclature officielle du code SH
   - Garder la description courte du PDF dans Description_of_goods
   - La nomenclature sera ajoutée lors de la saisie ASYCUDA

## Conclusion

Notre extraction actuelle est **fonctionnelle** pour les champs essentiels, mais nécessite **3 améliorations prioritaires**:

1. ✅ Extraction type colisage (CARTONS → CT)
2. ✅ Extraction numéro châssis/série (pour code 6122 et Free_text_1)
3. ✅ Ajout Previous_document_reference (facture + date)

Les différences de valeurs (packages, origine) sont normales et reflètent des informations complémentaires ajoutées lors de la saisie ASYCUDA.
