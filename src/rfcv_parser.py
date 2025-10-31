"""
Module de parsing des documents PDF RFCV
Extrait les données structurées et les mappe aux modèles
"""
import re
import math
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from pdf_extractor import PDFExtractor
from models import (
    RFCVData, Identification, Trader, Country, TransportInfo,
    Financial, Bank, Valuation, Container, Item, Property,
    AttachedDocument, Package, HSCode, Tarification, SupplementaryUnit,
    Taxation, TaxationLine, ValuationItem, CurrencyAmount
)
from hs_code_rules import HSCodeAnalyzer
from proportional_calculator import ProportionalCalculator
from item_grouper import group_items_by_hs_code

logger = logging.getLogger(__name__)


class RFCVParser:
    """Parser pour documents RFCV"""

    def __init__(self, pdf_path: str, taux_douane: Optional[float] = None):
        """
        Initialise le parser

        Args:
            pdf_path: Chemin vers le PDF RFCV
            taux_douane: Taux de change douanier pour calcul assurance (format: 566.6700)
        """
        self.pdf_path = pdf_path
        self.taux_douane = taux_douane
        self.text = ""
        self.tables = []

    def parse(self) -> RFCVData:
        """
        Parse le PDF et retourne les données structurées

        Returns:
            Objet RFCVData contenant toutes les données extraites
        """
        with PDFExtractor(self.pdf_path) as extractor:
            self.text = extractor.extract_all_text()
            self.tables = extractor.extract_all_tables()

        rfcv_data = RFCVData()

        # Parse toutes les sections
        rfcv_data.property = self._parse_property()
        rfcv_data.identification = self._parse_identification()
        rfcv_data.exporter = self._parse_exporter()
        rfcv_data.consignee = self._parse_consignee()
        rfcv_data.declarant = self._parse_declarant()
        rfcv_data.country = self._parse_country()
        rfcv_data.transport = self._parse_transport()
        rfcv_data.financial = self._parse_financial()
        rfcv_data.valuation = self._parse_valuation()
        rfcv_data.containers = self._parse_containers()
        rfcv_data.items = self._parse_items()
        rfcv_data.value_details = self._extract_value_details()

        # Regrouper les articles sans châssis par code HS
        # Seul le premier article du premier groupe aura quantité = total_packages
        # Tous les autres articles auront quantité = 0
        if rfcv_data.items and rfcv_data.property:
            total_packages = rfcv_data.property.total_packages
            rfcv_data.items = group_items_by_hs_code(rfcv_data.items, total_packages)

        # Enrichir les items avec les documents attachés
        self._add_attached_documents(rfcv_data)

        # Ajouter Summary_declaration (Bill of Lading) à tous les items
        if rfcv_data.transport and rfcv_data.transport.bill_of_lading:
            for item in rfcv_data.items:
                item.summary_declaration = rfcv_data.transport.bill_of_lading

        # Ajouter Previous_document_reference (Facture DU Date) au premier article uniquement
        if rfcv_data.financial and rfcv_data.financial.invoice_number and rfcv_data.items:
            invoice_num = rfcv_data.financial.invoice_number
            invoice_date = rfcv_data.financial.invoice_date

            # Format: "2025/BC/SN18215 DU 17/07/2025"
            if invoice_date:
                prev_doc_ref = f"{invoice_num} DU {invoice_date}"
            else:
                prev_doc_ref = invoice_num

            # Ajouter uniquement au premier article
            rfcv_data.items[0].previous_document_reference = prev_doc_ref

        # Enrichir ValuationItem.invoice avec les données de devise pour chaque item
        if rfcv_data.financial and rfcv_data.financial.currency_code and rfcv_data.financial.exchange_rate:
            for item in rfcv_data.items:
                if item.valuation_item and item.tarification and item.tarification.item_price:
                    # Utiliser item_price (valeur FOB de l'item) pour créer Item_Invoice
                    fob_value = item.tarification.item_price
                    rate_value = rfcv_data.financial.exchange_rate
                    item.valuation_item.invoice = CurrencyAmount(
                        amount_foreign=fob_value,
                        amount_national=fob_value * rate_value if fob_value and rate_value else None,
                        currency_code=rfcv_data.financial.currency_code,
                        currency_name='Pas de devise étrangère',
                        currency_rate=rate_value
                    )

        # Appliquer les calculs de répartition proportionnelle
        # Distribue FRET, ASSURANCE, POIDS BRUT, POIDS NET sur les articles
        # proportionnellement à leur FOB en utilisant la méthode du reste le plus grand
        calculator = ProportionalCalculator()
        rfcv_data = calculator.apply_to_rfcv(rfcv_data)

        # NOTE: La répartition du nombre de colis est maintenant gérée par le regroupement d'articles
        # Le nombre de colis (section 24) est stocké comme quantité du premier article du premier groupe
        # Tous les autres articles ont une quantité de 0

        return rfcv_data

    def _extract_field(self, pattern: str, group: int = 1) -> Optional[str]:
        """Extrait un champ avec regex

        Args:
            pattern: Pattern regex à rechercher
            group: Numéro du groupe de capture à extraire (défaut: 1)
        """
        match = re.search(pattern, self.text, re.IGNORECASE | re.MULTILINE)
        if match:
            try:
                return match.group(group).strip()
            except IndexError:
                return match.group(1).strip() if match.lastindex else match.group(0).strip()
        return None

    def _parse_property(self) -> Property:
        """Parse les propriétés du formulaire"""
        prop = Property()

        # Extraction du nombre de pages
        page_match = self._extract_field(r'PAGE\s+(\d+)\s+de\s+(\d+)')
        if page_match:
            parts = page_match.split('de')
            if len(parts) == 2:
                prop.form_number = int(parts[0].strip())
                prop.total_forms = int(parts[1].strip())

        # Total packages - Chercher le nombre dans la section 24
        # Pattern: "216 CARTONS" ou "216 PACKAGES" ou "216 COLIS"
        packages_match = self._extract_field(r'(\d+)\s+(?:CARTONS|PACKAGES|COLIS|PALETTES|PIECES)', re.IGNORECASE)
        if packages_match:
            prop.total_packages = int(packages_match)

        # P3.4: Type de colisage - Section 24
        # Structure: "24. Colisage, nombre et désignation des marchandises\n...\n<nombre> <TYPE>"
        # Types possibles: CARTONS, PACKAGES, COLIS, PALETTES, PIECES, etc.
        # Pattern: cherche un nombre suivi d'un type de colisage en majuscules
        package_type_match = self._extract_field(r'\d+\s+(CARTONS|PACKAGES|COLIS|PALETTES|PIECES|BAGS|BOXES)')
        if package_type_match:
            prop.package_type = package_type_match

        prop.sad_flow = 'I'  # Import par défaut
        prop.selected_page = 1

        return prop

    def _parse_identification(self) -> Identification:
        """Parse les informations d'identification"""
        ident = Identification()

        # P2.4: Numéro RFCV - Extraction corrigée
        # Structure PDF: "1. ... Code : XXX 4. No. RFCV 5. Date RFCV 6. Livraison\n<nom> <RCS_NUMBER> <date> <TOT/PART>"
        # Le numéro RFCV est le code RCS (ex: RCS25119416)
        # Pattern: cherche "RCS" suivi de chiffres sur la ligne après "4. No. RFCV"
        # Note: manifest_reference n'est plus utilisé (mis à null dans XML)

        # P3.3: Date RFCV - Section 5
        # Structure: "4. No. RFCV 5. Date RFCV 6. Livraison\n<nom> <RCS> <date_rfcv> <TOT/PART>"
        # La date RFCV est entre le numéro RCS et le type de livraison (format: DD/MM/YYYY)
        # P3.3: No. RFCV - Section 4
        # Structure: "4. No. RFCV 5. Date RFCV 6. Livraison\n<nom> RCS<numero> <date> <type>"
        rfcv_number = self._extract_field(r'4\.\s*No\.\s*RFCV.*?\n.*?(RCS\d+)')
        if rfcv_number:
            ident.rfcv_number = rfcv_number

        rfcv_date = self._extract_field(r'4\.\s*No\.\s*RFCV.*?\n.*?RCS\d+\s+(\d{2}/\d{2}/\d{4})')
        if rfcv_date:
            ident.rfcv_date = rfcv_date

        # P3.3: Type de Livraison - Section 6
        # Structure: Même ligne, après la date RFCV (TOT ou PART)
        delivery_type = self._extract_field(r'4\.\s*No\.\s*RFCV.*?\n.*?RCS\d+\s+\d{2}/\d{2}/\d{4}\s+(TOT|PART)')
        if delivery_type:
            ident.delivery_type = delivery_type

        # P3.3: No. FDI/DAI - Section 7
        # Structure: "7. No. FDI/DAI 8. Date FDI/DAI\n<numero_fdi> <date_fdi>"
        # Le numéro FDI est avant la date sur la ligne suivante
        fdi_number = self._extract_field(r'7\.\s*No\.\s*FDI/DAI.*?\n.*?([A-Z0-9\-]+)\s+\d{2}/\d{2}/\d{4}')
        if fdi_number:
            ident.fdi_number = fdi_number

        # P3.3: Date FDI/DAI - Section 8
        # Structure: Même ligne que le numéro FDI
        fdi_date = self._extract_field(r'7\.\s*No\.\s*FDI/DAI.*?\n.*?[A-Z0-9\-]+\s+(\d{2}/\d{2}/\d{4})')
        if fdi_date:
            ident.fdi_date = fdi_date

        # Type de déclaration (Import)
        ident.type_of_declaration = 'IM'
        ident.declaration_procedure_code = '4'

        # Bureau de douane (par défaut Abidjan)
        ident.customs_office_code = 'CIAB1'
        ident.customs_office_name = 'ABIDJAN-PORT'

        return ident

    def _parse_consignee(self) -> Trader:
        """Parse les informations du destinataire (importateur)"""
        consignee = Trader()

        # Code importateur
        code_match = self._extract_field(r'Code\s*[:\s]+(\w+)')
        if code_match:
            consignee.code = code_match

        # Nom et adresse importateur (section 1) - Pattern pour structure réelle
        # Structure: "1. Nom et Adresse de l'Importateur Code : XXX ..." sur une ligne
        # Puis le nom sur la ligne suivante avec RCS, dates, etc.
        # Note: caractère apostrophe peut être ' ou ' (U+2019)
        name_pattern = r"1\.\s*Nom et Adresse de l['\u2019]Importateur[^\n]*\n([^\n]+)"
        name_match = re.search(name_pattern, self.text, re.IGNORECASE)

        if name_match:
            first_line = name_match.group(1).strip()
            # Extraire le nom avant RCS, dates, ou autre data
            # Pattern: nom jusqu'à RCS ou date (DD/MM/YYYY) ou TOT/PART
            name_parts = re.split(r'\s+RCS|\s+\d{2}/\d{2}/\d{4}|\s+TOT|\s+PART', first_line)
            if name_parts and name_parts[0].strip():
                consignee.name = name_parts[0].strip()

        # Chercher l'adresse (ligne avec BP)
        if consignee.name:
            # Chercher après le nom
            address_pattern = r"1\.\s*Nom et Adresse de l['\u2019]Importateur[^\n]*\n[^\n]+\n[^\n]*\n([^\n]*BP[^\n]+)"
            address_match = re.search(address_pattern, self.text, re.IGNORECASE)
            if address_match:
                # Nettoyer l'adresse (enlever les numéros de suivi)
                addr = address_match.group(1).strip()
                # Prendre jusqu'au premier numéro long (>6 chiffres) qui est probablement un numéro de doc
                addr_parts = re.split(r'\s+-\s+\d{7,}', addr)
                consignee.address = addr_parts[0].strip()

        return consignee

    def _parse_exporter(self) -> Trader:
        """Parse les informations de l'exportateur"""
        exporter = Trader()

        # Nom et adresse exportateur (section 2) - Pattern pour structure réelle
        # Structure: "2. Nom et Adresse de l'Exportateur 11. Poids Total NET..." sur une ligne
        # Puis le nom sur la ligne suivante avec poids
        # Note: caractère apostrophe peut être ' ou ' (U+2019)
        name_pattern = r"2\.\s*Nom et Adresse de l['\u2019]Exportateur[^\n]*\n([^\n]+)"
        name_match = re.search(name_pattern, self.text, re.IGNORECASE)

        if name_match:
            first_line = name_match.group(1).strip()
            # Extraire le nom avant les chiffres de poids (format: "XX XXX,XX")
            # Le pattern de poids est typiquement: espace + nombres + espace + nombres avec virgule/point
            name_parts = re.split(r'\s+\d+\s+\d[\d\s,\.]+', first_line)
            if name_parts and name_parts[0].strip():
                exporter.name = name_parts[0].strip()

        # Chercher l'adresse (généralement 1-2 lignes après le nom)
        if exporter.name:
            # Pattern pour l'adresse qui peut contenir: ville, pays, etc.
            address_pattern = r"2\.\s*Nom et Adresse de l['\u2019]Exportateur[^\n]*\n[^\n]+\n[^\n]*\n([^\n]+)"
            address_match = re.search(address_pattern, self.text, re.IGNORECASE)
            if address_match:
                addr = address_match.group(1).strip()
                # Nettoyer: prendre jusqu'à la fin ou jusqu'à un pattern de section suivante
                # Arrêter avant les numéros de section (13., 14., etc.)
                addr_clean = re.split(r'\s+\d{2}\.\s+', addr)[0]
                if addr_clean and not addr_clean.startswith('13.') and not addr_clean.startswith('14.'):
                    exporter.address = addr_clean.strip()

        return exporter

    def _parse_declarant(self) -> Trader:
        """Parse les informations du déclarant"""
        # Le RFCV ne contient pas les informations du déclarant
        # Ces informations seront saisies manuellement dans ASYCUDA
        return Trader()

    def _parse_country(self) -> Country:
        """Parse les informations sur les pays"""
        country = Country()

        # P4.1: Pays de provenance - Section 9
        # Structure: "9. Pays de provenance 10. Mode de Paiement\n<PAYS> <mode_paiement>"
        # Le pays est le premier mot de la ligne suivante
        provenance = self._extract_field(r'9\.\s*Pays de provenance.*?\n([A-Za-zÀ-ÿ\s\'-]+?)\s+(?:Paiement|$)')
        if provenance:
            provenance = provenance.strip()
            country.export_country_name = provenance
            country.origin_country_name = provenance

            # P4.1: Mapper nom pays → code ISO (enrichir selon besoins)
            country_codes = {
                'Chine': 'CN',
                'China': 'CN',
                'Emirats Arabes Unis': 'AE',
                'United Arab Emirates': 'AE',
                'UAE': 'AE',
                'France': 'FR',
                'Allemagne': 'DE',
                'Germany': 'DE',
                'Italie': 'IT',
                'Italy': 'IT',
                'Espagne': 'ES',
                'Spain': 'ES',
                'Turquie': 'TR',
                'Turkey': 'TR'
            }

            for country_name, code in country_codes.items():
                if country_name.lower() in provenance.lower():
                    country.export_country_code = code
                    country.first_destination = code
                    break

        # Pays de destination (Côte d'Ivoire)
        country.destination_country_code = 'CI'
        country.destination_country_name = "Cote d'Ivoire"
        country.trading_country = 'CI'

        return country

    def _parse_transport(self) -> TransportInfo:
        """Parse les informations de transport"""
        transport = TransportInfo()

        # Mode de transport
        mode_match = self._extract_field(r'Mode de Transport[:\s]+(.*?)(?:\n|$)')
        if mode_match:
            if 'maritime' in mode_match.lower():
                transport.border_mode = '1'

        # Nom du navire/transporteur
        vessel_match = self._extract_field(r'Transporteur ID[:\s]+(.*?)(?:\n|$)')
        if vessel_match:
            transport.vessel_identity = vessel_match
            # P1.5: Extraire le nom du navire sans la date (format: "DD/MM/YYYY NOM_NAVIRE")
            # Supprimer la date au début si présente
            vessel_name_clean = re.sub(r'^\d{2}/\d{2}/\d{4}\s+', '', vessel_match.strip())
            transport.vessel_name = vessel_name_clean

        # P1.3: INCOTERM - Chercher pattern CFR/FOB/CIF/etc. après "15. INCOTERM"
        # Structure: "15. INCOTERM\n<texte>\n<date> <INCOTERM>"
        incoterm = self._extract_field(r'15\.\s*INCOTERM\s*\n.*?\n.*?\s([A-Z]{2,3})\s*\n')
        if not incoterm:
            # Pattern alternatif: chercher CFR, FOB, CIF, EXW, etc.
            incoterm_match = re.search(r'\b(CFR|FOB|CIF|EXW|FCA|CPT|CIP|DAP|DPU|DDP)\b', self.text)
            if incoterm_match:
                incoterm = incoterm_match.group(1)
        if incoterm:
            transport.delivery_terms_code = incoterm
            transport.incoterm = incoterm  # P1.3: Nouveau champ

        # P1.4: No. Connaissement (Bill of Lading) - chercher le numéro alphanumérique (6+ caractères)
        # Structure: Le BL est sur la 3ème ligne après "No. (LTA/Connaissement"
        # Exemples: 258614991 (numérique), COSU6426271870 (alphanumérique)
        bl_number = self._extract_field(r'No\.\s*\(LTA/Connaissement/CMR\):.*?\n.*?\n([A-Z0-9]{6,})')
        if bl_number:
            transport.bill_of_lading = bl_number

        # P1.4: Date Connaissement - chercher dans la section "3. Détails Transport"
        bl_date = self._extract_field(r'Date\s*de\s*\(LTA/Connaissement/CMR\):.*?\n(\d{2}/\d{2}/\d{4})')
        if bl_date:
            transport.bl_date = bl_date

        # P1.5: No. Voyage - chercher après "No. (Vol/Voyage/Transport routier):"
        # Structure: Le voyage est 2 lignes après
        voyage = self._extract_field(r'No\.\s*\(Vol/Voyage/Transport routier\):.*?\n.*?\n(\w+)\s*\n')
        if voyage:
            transport.voyage_number = voyage

        # P1.6 + P4.2: Lieu de chargement - non utilisé (mis à null dans XML)
        # Note: loading_place_code et loading_place_name ne sont plus extraits

        # P1.6: Lieu de déchargement
        unloading = self._extract_field(r'Lieu\s*de\s*déchargement:\s*([A-Z]{5})')
        if unloading:
            transport.location_of_goods = unloading
            transport.discharge_location = unloading  # P1.6: Nouveau champ

        # P1.6: Nombre de conteneurs FCL
        fcl_match = self._extract_field(r'No\.\s*de\s*FCL:\s*(\d+)')
        if fcl_match:
            fcl_count = int(fcl_match)
            transport.fcl_count = fcl_count
            if fcl_count > 0:
                transport.container_flag = True

        # P1.6: Nombre de conteneurs LCL
        lcl_match = self._extract_field(r'No\.\s*de\s*LCL:\s*(\d+)')
        if lcl_match:
            transport.lcl_count = int(lcl_match)

        transport.border_office_code = 'CIAB1'
        transport.border_office_name = 'ABIDJAN-PORT'

        return transport

    def _parse_financial(self) -> Financial:
        """Parse les informations financières"""
        financial = Financial()

        # Mode de paiement
        payment_mode = self._extract_field(r'10\.\s*Mode de Paiement[:\s]+(.*?)(?:\n|$)')
        if payment_mode:
            financial.mode_of_payment = payment_mode

        # Banque (à extraire si présent dans le document)
        financial.transaction_code1 = '0'
        financial.transaction_code2 = '1'

        # P2.2: No. Facture - Section 13
        # Structure: "13. No. Facture 14. Date Facture 15. INCOTERM\n<texte>\n<no_facture> <date> <incoterm>"
        invoice_number = self._extract_field(r'13\.\s*No\.\s*Facture\s+14\..*?\n.*?\n(\S+)\s+\d{2}/\d{2}/\d{4}')
        if invoice_number:
            financial.invoice_number = invoice_number

        # P2.2: Date Facture - Section 14
        # Même ligne que le numéro de facture
        invoice_date = self._extract_field(r'13\.\s*No\.\s*Facture\s+14\..*?\n.*?\n\S+\s+(\d{2}/\d{2}/\d{4})')
        if invoice_date:
            financial.invoice_date = invoice_date

        # P2.2: Total Facture - Section 18
        # NOTE: Section 18 (Total Facture) n'est PAS utilisée par ASYCUDA
        # Mise à null en attendant identification de la valeur correcte
        financial.invoice_amount = None

        # P2.3: Code Devise - Section 16
        # Structure: "16. Code Devise 17...\n<pays> <CODE> <taux> <montant>"
        currency_code = self._extract_field(r'16\.\s*Code\s*Devise\s+17\..*?\n.*?\s([A-Z]{3})\s+[\d\s,]+')
        if currency_code:
            financial.currency_code = currency_code

        # P2.3: Taux de Change - Section 17
        # Même ligne: "<pays> USD <taux> <montant_facture>"
        # Le taux est entre le code devise (USD) et le montant facture
        # Pattern: capture le nombre après USD (format français avec virgule)
        exchange_rate = self._extract_field(r'16\.\s*Code\s*Devise\s+17\..*?\n.*?\s[A-Z]{3}\s+([\d\s]+,\d{2,4})')
        if exchange_rate:
            financial.exchange_rate = self._parse_number(exchange_rate)

        return financial

    def _parse_valuation(self) -> Valuation:
        """Parse les informations de valorisation globale"""
        valuation = Valuation()

        valuation.calculation_mode = '2'

        # P1.7: Poids net et brut totaux - Sections 11 et 12
        # Structure: "2. Nom et Adresse de l'Exportateur 11. Poids Total NET 12. Poids Total BRUT"
        # Ligne suivante: "NOM_EXPORTATEUR POIDS_NET POIDS_BRUT"
        # Les poids sont sur la même ligne que le nom de l'exportateur (après le nom)
        # Format: "XX XXX,XX" (avec espaces pour milliers et virgule pour décimales)

        # Section 11: Poids Total NET (premier nombre après le nom de l'exportateur)
        net_weight_str = self._extract_field(r'11\.\s*Poids Total NET.*?\n.*?(\d[\d\s]+,\d{2})\s+\d[\d\s]+,\d{2}')
        if net_weight_str:
            valuation.net_weight = self._parse_number(net_weight_str)

        # Section 12: Poids Total BRUT (deuxième nombre après le nom de l'exportateur)
        gross_weight_str = self._extract_field(r'12\.\s*Poids Total BRUT.*?\n.*?\d[\d\s]+,\d{2}\s+(\d[\d\s]+,\d{2})')
        if gross_weight_str:
            valuation.gross_weight = self._parse_number(gross_weight_str)

        valuation.total_weight = valuation.gross_weight  # Total weight = gross weight

        # P2.3: Code Devise - chercher le code ISO 3 lettres sur la ligne suivante
        # Structure: "16. Code Devise 17. Taux...\n<pays> <CODE_ISO> <taux> <montant>"
        # Note: utilise [^\n] au lieu de . car _extract_field n'utilise pas re.DOTALL
        currency = self._extract_field(r'16\.\s*Code Devise[^\n]*?17\.[^\n]*?\n[^\n]*?([A-Z]{3})\s+[\d\s,]+')

        # P2.4: Taux de Change - chercher le taux après le code devise
        # Structure: même ligne que devise, format: "USD 566,6700"
        currency_rate = self._extract_field(r'16\.\s*Code Devise[^\n]*?17\.[^\n]*?\n[^\n]*?[A-Z]{3}\s+([\d\s]+,\d{2,4})')

        # P4.3: FOB - Structure: "19. Total Valeur FOB attestée 20. Fret Attesté\n3. Détails Transport\n<FOB> <FRET>"
        # Pattern: premier nombre sur ligne après "3. Détails Transport"
        # NOTE IMPORTANTE: Section 19 (Total Valeur FOB attestée) EST utilisée pour Gs_Invoice dans ASYCUDA
        #                  Section 18 (Total Facture) n'est PAS utilisée (différent du FOB)
        #                  Section 20 (Fret Attesté) n'est PAS utilisée directement
        fob = self._extract_field(r'19\.\s*Total Valeur FOB.*?\n.*?\n([\d\s]+,\d{2})\s+[\d\s]+,\d{2}')

        # P4.3: Assurance - Section 21 (Assurance Attestée)
        # NOTE: L'assurance est une valeur calculée par ASYCUDA, pas extraite du RFCV
        # Mise à null en attendant la formule de calcul

        # CIF - Pattern amélioré pour capturer les valeurs avec espaces et formats variés
        cif = self._extract_field(r'23\.\s*Valeur CIF Attestée[:\s]+([\d][\d\s,\.]+)')

        # Si le pattern simple ne marche pas, chercher dans le contexte plus large
        if not cif:
            cif_pattern = r'Valeur CIF[^\d]*([\d][\d\s,\.]+)'
            match = re.search(cif_pattern, self.text, re.IGNORECASE)
            if match:
                cif = match.group(1).strip()

        # Créer les CurrencyAmount
        # Gs_Invoice: Utilise la section 19 (Total Valeur FOB attestée)
        if fob and currency and currency_rate:
            fob_value = self._parse_number(fob)
            rate_value = self._parse_number(currency_rate)
            valuation.invoice = CurrencyAmount(
                amount_foreign=fob_value,
                amount_national=fob_value * rate_value if fob_value and rate_value else None,
                currency_code=currency,
                currency_name='Pas de devise étrangère',
                currency_rate=rate_value
            )
        else:
            valuation.invoice = None

        # Section 20: Fret Attesté (external_freight)
        # Structure: "19. Total Valeur FOB attestée 20. Fret Attesté\n3. Détails Transport\n<FOB> <FRET>"
        # Le FRET est le deuxième nombre sur la ligne après "3. Détails Transport"
        fret_str = self._extract_field(r'19\.\s*Total Valeur FOB.*?\n.*?\n[\d\s]+,\d{2}\s+([\d\s]+,\d{2})')
        if fret_str and currency and currency_rate:
            fret_value = self._parse_number(fret_str)
            rate_value = self._parse_number(currency_rate)
            if fret_value is not None:
                valuation.external_freight = CurrencyAmount(
                    amount_foreign=fret_value,
                    amount_national=fret_value * rate_value if rate_value else None,
                    currency_code=currency,
                    currency_name='Pas de devise étrangère',
                    currency_rate=rate_value
                )
        else:
            valuation.external_freight = None

        # Section 21: Assurance - CALCUL selon nouvelle formule douanière
        # Formule : 2500 + (FOB + FRET) × TAUX_DOUANE × 0.15%
        # FOB: section 19 (Total Valeur FOB attestée)
        # FRET: section 20 (Fret Attesté)
        # TAUX_DOUANE: fourni par l'utilisateur (variable selon la douane)
        # Résultat: toujours en XOF avec taux 1.0

        if fob and fret_str and self.taux_douane:
            fob_value = self._parse_number(fob)
            fret_value = self._parse_number(fret_str)

            if fob_value is not None and fret_value is not None and fob_value > 0 and fret_value > 0:
                # Calcul : 2500 + (FOB + FRET) × TAUX × 0.0015
                # Arrondi à l'entier supérieur (ceiling) pour avoir un montant entier
                assurance_xof = math.ceil(2500 + (fob_value + fret_value) * self.taux_douane * 0.0015)

                valuation.insurance = CurrencyAmount(
                    amount_national=assurance_xof,
                    amount_foreign=assurance_xof,  # XOF: amount_national = amount_foreign
                    currency_code='XOF',
                    currency_name='Franc CFA',
                    currency_rate=1.0
                )
            else:
                # FOB ou FRET manquant/invalide → assurance à null
                valuation.insurance = None
        else:
            # Données insuffisantes pour calcul → assurance à null
            valuation.insurance = None

        # Total_invoice: Utilise la valeur FOB (section 19) en devise étrangère
        # Note: Section 18 (Total Facture) n'est pas la même que le FOB
        valuation.total_invoice = self._parse_number(fob) if fob else None

        # TODO: Total_cost et Total_CIF à null en attendant clarification
        # Incohérence détectée:
        # - Total_cost calculé comme FOB+Fret+Assurance+Charges ne correspond pas à ASYCUDA
        # - Total_CIF extraction capture le numéro de connaissement au lieu du CIF
        # Dans ASYCUDA: Total_cost = Somme(Item/Total_cost_itm), Total_CIF = Somme(Item/Total_CIF_itm)
        valuation.total_cost = None
        valuation.total_cif = None

        return valuation

    def _parse_containers(self) -> List[Container]:
        """Parse la liste des conteneurs"""
        containers = []

        # Chercher la section conteneurs dans le texte
        container_section = re.search(
            r'26\.\s*Conteneurs(.*?)(?:26\.\s*Articles|$)',
            self.text,
            re.DOTALL | re.IGNORECASE
        )

        if container_section:
            section_text = container_section.group(1)

            # Pattern pour extraire les conteneurs
            # Format: N No_Conteneur Type Taille No_Scellé
            # Exemple: "1 MRSU7172203 Conteneur 40' High cube 40' ML-CN8063134"
            container_pattern = r'(\d+)\s+(\w+)\s+Conteneur\s+(\d+\'.*?)\s+(\d+\')\s+(\w+)'

            for match in re.finditer(container_pattern, section_text):
                # Déterminer le type de conteneur selon codes ISO
                size = match.group(4).replace("'", "")  # "20", "40", "45"
                description = match.group(3).lower()     # "40' high cube", "20' refrigerated", etc.

                # Mapping des types de conteneurs ISO
                # Format: [Taille][Type] - ex: 40HC, 20GP, 45HC, 40RF, 40OT, etc.
                type_mapping = {
                    'high cube': 'HC',      # High Cube (9'6" height)
                    'high-cube': 'HC',
                    'open top': 'OT',       # Open Top
                    'flat rack': 'FR',      # Flat Rack
                    'flat-rack': 'FR',
                    'refrigerated': 'RF',   # Refrigerated/Reefer
                    'reefer': 'RF',
                    'tank': 'TK',           # Tank container
                    'standard': 'GP',       # General Purpose (standard)
                }

                # Déterminer le suffix selon la description
                container_suffix = 'GP'  # Par défaut: General Purpose
                for keyword, suffix in type_mapping.items():
                    if keyword in description:
                        container_suffix = suffix
                        break

                container_type = f"{size}{container_suffix}"

                container = Container(
                    item_number=int(match.group(1)),
                    identity=match.group(2),
                    container_type=container_type,
                    empty_full_indicator='1/1'
                )
                containers.append(container)

        return containers

    def _parse_items(self) -> List[Item]:
        """Parse la liste des articles"""
        items = []

        # Chercher la section articles
        articles_section = re.search(
            r'26\.\s*Articles(.*?)$',
            self.text,
            re.DOTALL | re.IGNORECASE
        )

        if not articles_section:
            return items

        section_text = articles_section.group(1)

        # Extraire le type de colisage de la section 24
        package_type_match = self._extract_field(r'\d+\s+(CARTONS|PACKAGES|COLIS|PALETTES|PIECES|BAGS|BOXES)')
        kind_code, kind_name = self._map_package_type(package_type_match)

        # Pattern pour extraire les articles
        # Format: N° Quantité UM UPO Origine Description Code_SH Valeur_FOB Valeur_taxable
        # Note: Les nombres peuvent contenir des espaces (ex: "2 000,00")
        item_pattern = r'(\d+)\s+([\d\s]+,\d{2})\s+(\w+)\s+(\w+)\s+(\w+)\s+(.*?)\s+(\d{4}\.\d{2}\.\d{2}\.\d{2})\s+([\d\s]+,\d{2})\s+([\d\s]+,\d{2})'

        # Extraire la description commerciale depuis la ligne précédant les données de l'article
        # La description est sur la ligne avant "1 36 000,00 KG N CN..."
        commercial_description = None
        lines = section_text.split('\n')
        for i, line in enumerate(lines):
            # Chercher la ligne avec le numéro d'article et les données
            if re.match(r'^\d+\s+[\d\s]+,\d{2}\s+\w+\s+\w+\s+\w+', line):
                # La description est dans les lignes précédentes (après les en-têtes)
                for j in range(i-1, -1, -1):
                    if lines[j].strip() and not lines[j].strip().startswith(('A ', 'R ', 'T ', 'I ', 'C ', 'L ', 'E ')):
                        # Ligne de description trouvée
                        desc_full = lines[j].strip()
                        # Prendre la partie avant la parenthèse si présente
                        commercial_description = desc_full.split('(')[0].strip()
                        break
                break

        for match in re.finditer(item_pattern, section_text):
            item = Item()

            # Extraire la quantité et l'unité de mesure de l'article
            quantity = self._parse_number(match.group(2))  # Ex: "36 000,00" -> 36000
            unit_measure = match.group(3)  # Ex: "KG"

            # Description brute
            raw_description = match.group(6).strip()

            # HS Code - extraction préalable pour analyse
            hs_code_str = match.group(7)
            # Remove dots from HS code (e.g., "2803.00.00.00" -> "2803000000")
            hs_code_clean = hs_code_str.replace('.', '')

            # DÉTECTION CHÂSSIS: Analyser si l'article nécessite un châssis
            chassis_info = HSCodeAnalyzer.requires_chassis(hs_code_clean, raw_description)

            chassis_number = None
            goods_description_clean = raw_description
            marks2_value = None

            if chassis_info['required']:
                # Tenter d'extraire le châssis
                chassis_number = self._extract_chassis_number(raw_description)

                if chassis_number:
                    # Châssis trouvé: nettoyer la description
                    goods_description_clean = raw_description.replace(chassis_number, '').strip()
                    goods_description_clean = re.sub(r'\s+', ' ', goods_description_clean)

                    # Format ASYCUDA: "CH: XXXXX"
                    marks2_value = f"CH: {chassis_number}"

                    logger.info(
                        f"Article {match.group(1)}: Châssis détecté ({chassis_info['category']}) "
                        f"- {chassis_number}"
                    )
                else:
                    # ⚠️ Châssis attendu mais non trouvé
                    logger.warning(
                        f"Article {match.group(1)}: Code HS {hs_code_clean[:4]} nécessite un châssis "
                        f"({chassis_info['category']}, confiance: {chassis_info['confidence']:.0%}) "
                        f"mais aucun numéro détecté dans: {raw_description[:60]}..."
                    )

            # Description finale
            item.goods_description = goods_description_clean

            # Package info avec châssis si présent
            item.packages = Package(
                number_of_packages=None,  # Sera calculé après depuis total_packages (Section 24)
                kind_code=kind_code,
                kind_name=kind_name,
                marks1=commercial_description if commercial_description else goods_description_clean,
                marks2=marks2_value,  # "CH: XXXXX" ou None
                chassis_number=chassis_number  # Numéro brut pour référence
            )
            item.country_of_origin_code = match.group(5)

            # Summary declaration sera ajouté après parsing (besoin du bill_of_lading)
            item.tarification = Tarification(
                hscode=HSCode(
                    commodity_code=hs_code_clean[:8] if len(hs_code_clean) >= 8 else hs_code_clean,
                    precision_1=hs_code_clean[8:10] if len(hs_code_clean) >= 10 else '00'
                ),
                extended_procedure='4000',
                national_procedure='000',
                supplementary_units=[],  # Null - ASYCUDA déterminera automatiquement selon code HS
                item_price=self._parse_number(match.group(8))
            )

            # Valuation item
            item.valuation_item = ValuationItem(
                total_cost=self._parse_number(match.group(8)),
                total_cif=self._parse_number(match.group(9))
            )

            # Taxation vide par défaut
            item.taxation = Taxation(
                item_taxes_amount=0.0,
                item_taxes_guaranteed=0.0,
                taxation_lines=[]
            )

            items.append(item)

        return items

    def _extract_value_details(self) -> Optional[float]:
        """Extrait la valeur totale des détails"""
        # Utilise la valeur CIF totale avec pattern amélioré
        cif = self._extract_field(r'23\.\s*Valeur CIF Attestée[:\s]+([\d][\d\s,\.]+)')

        # Fallback si le pattern simple ne marche pas
        if not cif:
            cif_pattern = r'Valeur CIF[^\d]*([\d][\d\s,\.]+)'
            match = re.search(cif_pattern, self.text, re.IGNORECASE)
            if match:
                cif = match.group(1).strip()

        if cif:
            return self._parse_number(cif)
        return None

    def _parse_number(self, value: str) -> Optional[float]:
        """
        Parse un nombre depuis une chaîne avec gestion des formats variés

        Args:
            value: Chaîne contenant le nombre

        Returns:
            Nombre float ou None
        """
        if not value:
            return None

        try:
            # Enlève les espaces
            cleaned = value.strip().replace(' ', '')
            # Remplace virgule par point
            cleaned = cleaned.replace(',', '.')
            return float(cleaned)
        except (ValueError, AttributeError):
            return None

    @staticmethod
    def _map_package_type(package_type: Optional[str]) -> tuple:
        """
        Mappe le type de colisage du PDF vers les codes ASYCUDA

        Args:
            package_type: Type extrait du PDF (CARTONS, PACKAGES, etc.)

        Returns:
            Tuple (code, nom) pour ASYCUDA
        """
        if not package_type:
            return ('PK', 'Colis ("package")')

        # Mapping des types de colisage vers codes ASYCUDA
        mapping = {
            'CARTONS': ('CT', 'Carton'),
            'PACKAGES': ('PK', 'Colis ("package")'),
            'COLIS': ('PK', 'Colis ("package")'),
            'PALETTES': ('PL', 'Palette'),
            'PIECES': ('PC', 'Pièce'),
            'BAGS': ('BG', 'Sac'),
            'BOXES': ('BX', 'Boîte'),
            'BARRELS': ('BA', 'Baril'),
            'DRUMS': ('DR', 'Fût'),
            'CONTAINERS': ('CN', 'Conteneur'),
        }

        # Recherche du type (insensible à la casse)
        package_upper = package_type.upper()
        if package_upper in mapping:
            return mapping[package_upper]

        # Par défaut: Package
        return ('PK', 'Colis ("package")')

    def _extract_chassis_number(self, description: str, expected_lengths: List[int] = None) -> Optional[str]:
        """
        Extrait un numéro de châssis depuis la description d'un véhicule

        Args:
            description: Description de la marchandise
            expected_lengths: Longueurs attendues (défaut: [13, 17])

        Returns:
            Numéro de châssis ou None

        Exemples:
            "TRICYCLE AP150ZH-20 LLCLHJL03SP420331" → "LLCLHJL03SP420331"
            "MOTORCYCLE LRFPCJLDIS0F18969" → "LRFPCJLDIS0F18969"
        """
        if not description:
            return None

        if expected_lengths is None:
            expected_lengths = [13, 17]

        # PATTERN 1: Châssis avec préfixe explicite
        # Exemples: "CH: XXXXX", "CHASSIS: XXXXX", "VIN: XXXXX"
        prefix_pattern = r'(?:CH|CHASSIS|VIN)[:\s]+([A-Z0-9]{13,17})'
        match = re.search(prefix_pattern, description, re.IGNORECASE)
        if match:
            chassis = match.group(1).upper()
            logger.debug(f"Châssis détecté (préfixe): {chassis}")
            return chassis

        # PATTERN 2: VIN standard (17 caractères)
        # Validation: pas de I, O, Q (norme ISO 3779)
        if 17 in expected_lengths:
            vin_pattern = r'\b([A-HJ-NPR-Z0-9]{17})\b'
            match = re.search(vin_pattern, description)
            if match:
                chassis = match.group(1).upper()
                logger.debug(f"VIN détecté (17 car): {chassis}")
                return chassis

        # PATTERN 3: Châssis fabricant (13-17 caractères alphanumériques)
        # Utilisé pour tricycles, motos, etc.
        for length in sorted(expected_lengths, reverse=True):
            pattern = rf'\b([A-Z0-9]{{{length}}})\b'
            matches = re.findall(pattern, description)

            for chassis in matches:
                # Validation: éviter faux positifs (codes HS, dates, etc.)
                # Un châssis doit avoir au moins des lettres ET des chiffres
                has_letters = any(c.isalpha() for c in chassis)
                has_digits = any(c.isdigit() for c in chassis)

                if has_letters and has_digits:
                    logger.debug(f"Châssis détecté ({length} car): {chassis}")
                    return chassis.upper()

        logger.debug(f"Aucun châssis détecté dans: {description[:50]}...")
        return None

    def _add_attached_documents(self, rfcv_data: RFCVData) -> None:
        """
        Ajoute les documents attachés standards à chaque item

        Documents standards ASYCUDA Côte d'Ivoire:
        - Code 0007: FACTURE (No. Facture + Date) - PREMIER ARTICLE UNIQUEMENT
        - Code 2501: A.V./R.F.C.V. - ATTESTATION DE VERIFICATION (No. RFCV) - TOUS LES ARTICLES
        - Code 6610: NUMERO FDI (No. FDI/DAI + Date) - TOUS LES ARTICLES

        Args:
            rfcv_data: Données RFCV complètes avec identification et financial
        """
        # Récupérer les références depuis identification et financial
        rfcv_number = rfcv_data.identification.rfcv_number if rfcv_data.identification else None
        fdi_number = rfcv_data.identification.fdi_number if rfcv_data.identification else None
        fdi_date = rfcv_data.identification.fdi_date if rfcv_data.identification else None
        invoice_number = rfcv_data.financial.invoice_number if rfcv_data.financial else None
        invoice_date = rfcv_data.financial.invoice_date if rfcv_data.financial else None

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
            # Document 2: RFCV (code 2501)
            if rfcv_number:
                item.attached_documents.append(AttachedDocument(
                    code='2501',
                    name="A.V./R.F.C.V. - ATTESTATION DE VERIFICATION",
                    reference=rfcv_number,
                    from_rule=1
                ))

            # Document 3: FDI (code 6610)
            if fdi_number:
                item.attached_documents.append(AttachedDocument(
                    code='6610',
                    name='NUMERO  FDI',
                    reference=fdi_number,
                    from_rule=1,
                    document_date=fdi_date
                ))


def parse_rfcv(pdf_path: str, taux_douane: Optional[float] = None) -> RFCVData:
    """
    Fonction utilitaire pour parser un PDF RFCV

    Args:
        pdf_path: Chemin du fichier PDF
        taux_douane: Taux de change douanier pour calcul assurance (optionnel)

    Returns:
        Données RFCV structurées
    """
    parser = RFCVParser(pdf_path, taux_douane=taux_douane)
    return parser.parse()
