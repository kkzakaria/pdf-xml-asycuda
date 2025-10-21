"""
Module de parsing des documents PDF RFCV
Extrait les données structurées et les mappe aux modèles
"""
import re
from typing import Optional, List, Dict, Any
from datetime import datetime
from pdf_extractor import PDFExtractor
from models import (
    RFCVData, Identification, Trader, Country, TransportInfo,
    Financial, Bank, Valuation, Container, Item, Property,
    AttachedDocument, Package, HSCode, Tarification, SupplementaryUnit,
    Taxation, TaxationLine, ValuationItem, CurrencyAmount
)


class RFCVParser:
    """Parser pour documents RFCV"""

    def __init__(self, pdf_path: str):
        """
        Initialise le parser

        Args:
            pdf_path: Chemin vers le PDF RFCV
        """
        self.pdf_path = pdf_path
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

        # Total packages
        packages_match = self._extract_field(r'(\d+)\s+PACKAGES')
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
        rfcv_number = self._extract_field(r'4\.\s*No\.\s*RFCV.*?\n.*?(RCS\d+)')

        ident.manifest_reference = rfcv_number

        # P3.3: Date RFCV - Section 5
        # Structure: "4. No. RFCV 5. Date RFCV 6. Livraison\n<nom> <RCS> <date_rfcv> <TOT/PART>"
        # La date RFCV est entre le numéro RCS et le type de livraison (format: DD/MM/YYYY)
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

        # Pays de provenance
        provenance = self._extract_field(r'9\.\s*Pays de provenance[:\s]+(.*?)(?:\n|$)')
        if provenance:
            country.export_country_name = provenance
            country.origin_country_name = provenance
            # Mapper nom pays → code (Chine = CN)
            if 'Chine' in provenance or 'China' in provenance:
                country.export_country_code = 'CN'
                country.first_destination = 'CN'

        # Pays de destination (Côte d'Ivoire)
        country.destination_country_code = 'CI'
        country.destination_country_name = "Cote d'Ivoire"

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

        # P1.4: No. Connaissement (Bill of Lading) - chercher le numéro long (6+ chiffres)
        # Structure: Le BL est sur la 3ème ligne après "No. (LTA/Connaissement"
        bl_number = self._extract_field(r'No\.\s*\(LTA/Connaissement/CMR\):.*?\n.*?\n(\d{6,})')
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

        # P1.6: Lieu de chargement (pattern amélioré pour code UN/LOCODE)
        loading = self._extract_field(r'Lieu\s*de\s*chargement:\s*([A-Z]{5})')
        if loading:
            transport.loading_place_code = loading
            transport.loading_location = loading  # P1.6: Nouveau champ

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
        # Structure: "16. Code Devise 17. Taux de Change 18. Total Facture\n<pays> USD <taux> <montant_facture>"
        # Le montant total facture est le DERNIER nombre sur la ligne après le code devise
        invoice_amount = self._extract_field(r'18\.\s*Total\s*Facture.*?\n.*?\s+([\d\s]+,\d{2})\s*$')
        if invoice_amount:
            financial.invoice_amount = self._parse_number(invoice_amount)

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

        # P1.7: Poids net total (pattern amélioré)
        # Structure: "11. Poids Total NET (KG) 12. Poids Total BRUT (KG)\n<nom> <poids NET> <poids BRUT>"
        # Les poids sont sur la même ligne après le nom
        # Pattern: capture nombre format français "24 687,00" (chiffres avec espaces + virgule + 2 décimales)
        net_weight = self._extract_field(r'11\.\s*Poids Total NET\s*\(KG\)\s+12\..*?\n.*?\s+([\d\s]+,\d{2})\s+([\d\s]+,\d{2})\s*\n')
        if net_weight:
            valuation.net_weight = self._parse_number(net_weight)
            valuation.total_weight = self._parse_number(net_weight)  # Rétro-compatibilité

        # P1.7: Poids brut total (pattern amélioré)
        # Structure: capture le 2ème nombre après le nom (sur même ligne)
        # Le pattern ci-dessus capture les 2 groupes, on extrait le 2ème
        gross_weight = self._extract_field(r'11\.\s*Poids Total NET\s*\(KG\)\s+12\..*?\n.*?\s+([\d\s]+,\d{2})\s+([\d\s]+,\d{2})\s*\n', group=2)
        if gross_weight:
            valuation.gross_weight = self._parse_number(gross_weight)

        # Devise
        currency = self._extract_field(r'16\.\s*Code Devise[:\s]+(\w+)')
        currency_rate = self._extract_field(r'17\.\s*Taux de Change[:\s]+([\d\s,\.]+)')

        # Total facture
        total_invoice = self._extract_field(r'18\.\s*Total Facture[:\s]+([\d\s,\.]+)')

        # FOB
        fob = self._extract_field(r'19\.\s*Total Valeur FOB attestée[:\s]+([\d\s,\.]+)')

        # Fret
        freight = self._extract_field(r'20\.\s*Fret Attesté[:\s]+([\d\s,\.]+)')

        # Assurance
        insurance = self._extract_field(r'21\.\s*Assurance Attestée[:\s]+([\d\s,\.]+)')

        # CIF - Pattern amélioré pour capturer les valeurs avec espaces et formats variés
        cif = self._extract_field(r'23\.\s*Valeur CIF Attestée[:\s]+([\d][\d\s,\.]+)')

        # Si le pattern simple ne marche pas, chercher dans le contexte plus large
        if not cif:
            cif_pattern = r'Valeur CIF[^\d]*([\d][\d\s,\.]+)'
            match = re.search(cif_pattern, self.text, re.IGNORECASE)
            if match:
                cif = match.group(1).strip()

        # Créer les CurrencyAmount
        valuation.invoice = CurrencyAmount(
            amount_foreign=self._parse_number(total_invoice) if total_invoice else None,
            currency_code=currency,
            currency_rate=self._parse_number(currency_rate) if currency_rate else None
        )

        valuation.external_freight = CurrencyAmount(
            amount_foreign=self._parse_number(freight) if freight else None,
            currency_code=currency,
            currency_rate=self._parse_number(currency_rate) if currency_rate else None
        )

        valuation.insurance = CurrencyAmount(
            amount_foreign=self._parse_number(insurance) if insurance else None,
            currency_code=currency,
            currency_rate=self._parse_number(currency_rate) if currency_rate else None
        )

        valuation.total_invoice = self._parse_number(total_invoice) if total_invoice else None
        valuation.total_cif = self._parse_number(cif) if cif else None
        valuation.total_cost = self._parse_number(fob) if fob else None

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
            container_pattern = r'(\d+)\s+(\w+)\s+Conteneur\s+(\d+\'.*?)\s+(\d+\')\s+(\w+)'

            for match in re.finditer(container_pattern, section_text):
                container = Container(
                    item_number=int(match.group(1)),
                    identity=match.group(2),
                    container_type=match.group(4).replace("'", ""),
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

        # Pattern pour extraire les articles
        # Format: N° Quantité UM UPO Description Code_SH Valeur_FOB Valeur_taxable
        item_pattern = r'(\d+)\s+([\d,\.]+)\s+(\w+)\s+(\w+)\s+(\w+)\s+(.*?)\s+(\d{4}\.\d{2}\.\d{2}\.\d{2})\s+([\d,\.]+)\s+([\d,\.]+)'

        for match in re.finditer(item_pattern, section_text):
            item = Item()

            # Package info
            item.packages = Package(
                number_of_packages=self._parse_number(match.group(2)),
                kind_code='PK',
                kind_name='Colis ("package")'
            )

            # Description
            item.goods_description = match.group(6).strip()
            item.country_of_origin_code = match.group(5)

            # HS Code
            hs_code_str = match.group(7)
            item.tarification = Tarification(
                hscode=HSCode(
                    commodity_code=hs_code_str[:8] if len(hs_code_str) >= 8 else hs_code_str,
                    precision_1=hs_code_str[8:10] if len(hs_code_str) >= 10 else '00'
                ),
                extended_procedure='4000',
                national_procedure='000',
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


def parse_rfcv(pdf_path: str) -> RFCVData:
    """
    Fonction utilitaire pour parser un PDF RFCV

    Args:
        pdf_path: Chemin du fichier PDF

    Returns:
        Données RFCV structurées
    """
    parser = RFCVParser(pdf_path)
    return parser.parse()
