# Tests des Modifications - Type Colisage et Previous_document_reference

## Modifications Implémentées

### 1. Type de Colisage (Kind_of_packages)
- **Ajout** de la méthode `_map_package_type()` dans `rfcv_parser.py`
- **Mapping** des types PDF vers codes ASYCUDA :
  - CARTONS → CT (Carton)
  - PACKAGES → PK (Colis "package")
  - COLIS → PK
  - PALETTES → PL
  - PIECES → PC
  - BAGS → BG
  - BOXES → BX
  - etc.

### 2. Previous_document_reference
- **Ajout** du champ `previous_document_reference` au modèle `Item`
- **Format** : "{invoice_number} DU {invoice_date}"
- **Population** automatique pour tous les items

## Résultats des Tests

| PDF Testé | Type Colisage PDF | Code XML | Previous_doc_ref | Statut |
|-----------|-------------------|----------|------------------|---------|
| BL_2025_03228_RFCV.pdf | 257 PACKAGES | PK ✅ | 2025/GB/SN18125 DU 10/07/2025 ✅ | ✅ |
| OT_M_2025_03475_BL_2025_03320_RFCV_v1.pdf | 216 CARTONS | CT ✅ | 2025/BC/SN18215 DU 17/07/2025 ✅ | ✅ |
| DOSSIER 18237.pdf | 2679 PACKAGES | PK ✅ | 2025/BC/SN18237 DU 17/07/2025 ✅ | ✅ |

## Fichiers Modifiés

1. **src/models.py**
   - Ajout du champ `previous_document_reference: Optional[str]` au modèle `Item`

2. **src/rfcv_parser.py**
   - Ajout de la méthode `_map_package_type()` (lignes 674-708)
   - Modification de `_parse_items()` pour extraire et utiliser le type de colisage (lignes 583-603)
   - Ajout de la population de `previous_document_reference` dans `parse()` (lignes 66-78)

3. **src/xml_generator.py**
   - Modification de la génération de `Previous_document_reference` pour utiliser la valeur du modèle (ligne 600)

## Validation

✅ **Type de colisage** correctement extrait et mappé
✅ **Previous_document_reference** correctement formaté et rempli
✅ **3 PDFs** testés avec succès
✅ **Conformité ASYCUDA** vérifiée

## Conformité avec ASYCUDA de Référence

Comparaison avec IM18215.xml (motos) :
- ✅ Kind_of_packages_code: "CT" (CARTONS)
- ✅ Kind_of_packages_name: "Carton"
- ✅ Previous_document_reference: "{facture} DU {date}"

Format identique à ASYCUDA ✅
