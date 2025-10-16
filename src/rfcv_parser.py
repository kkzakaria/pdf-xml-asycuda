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

    def _extract_field(self, pattern: str) -> Optional[str]:
        """Extrait un champ avec regex"""
        match = re.search(pattern, self.text, re.IGNORECASE | re.MULTILINE)
        if match:
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

        prop.sad_flow = 'I'  # Import par défaut
        prop.selected_page = 1

        return prop

    def _parse_identification(self) -> Identification:
        """Parse les informations d'identification"""
        ident = Identification()

        # Numéro RFCV
        ident.manifest_reference = self._extract_field(r'No\.\s*RFCV[:\s]+(\S+)')

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

        # Nom et adresse importateur (section 1)
        name_pattern = r'1\.\s*Nom et Adresse de l\'Importateur.*?Code.*?\n(.*?)(?:\n\n|\n[0-9]\.|$)'
        name_match = re.search(name_pattern, self.text, re.DOTALL | re.IGNORECASE)
        if name_match:
            lines = name_match.group(1).strip().split('\n')
            if lines:
                consignee.name = lines[0].strip()
                if len(lines) > 1:
                    consignee.address = '\n'.join(lines[1:]).strip()

        return consignee

    def _parse_exporter(self) -> Trader:
        """Parse les informations de l'exportateur"""
        exporter = Trader()

        # Nom et adresse exportateur (section 2)
        name_pattern = r'2\.\s*Nom et Adresse de l\'Exportateur[:\s]+(.*?)(?:\n\n|\n[0-9]\.|Emirats|United)'
        name_match = re.search(name_pattern, self.text, re.DOTALL | re.IGNORECASE)
        if name_match:
            lines = name_match.group(1).strip().split('\n')
            if lines:
                # Première ligne = nom
                exporter.name = lines[0].strip()
                # Lignes suivantes = adresse
                if len(lines) > 1:
                    address_parts = []
                    for line in lines[1:]:
                        clean_line = line.strip()
                        if clean_line and not clean_line.startswith('Emirats'):
                            address_parts.append(clean_line)
                    if address_parts:
                        exporter.address = '\n'.join(address_parts)

        return exporter

    def _parse_declarant(self) -> Trader:
        """Parse les informations du déclarant"""
        # Pour RFCV, souvent le déclarant = importateur
        # À adapter selon structure exacte du document
        return self._parse_consignee()

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

        # INCOTERM
        incoterm = self._extract_field(r'15\.\s*INCOTERM[:\s]+(\w+)')
        if incoterm:
            transport.delivery_terms_code = incoterm

        # Lieu de chargement
        loading = self._extract_field(r'Lieu de chargement[:\s]+(\w+)')
        if loading:
            transport.loading_place_code = loading

        # Lieu de déchargement
        unloading = self._extract_field(r'Lieu de déchargement[:\s]+(\w+)')
        if unloading:
            transport.location_of_goods = unloading

        # Conteneurs
        fcl_match = self._extract_field(r'No\. de FCL[:\s]+(\d+)')
        if fcl_match and int(fcl_match) > 0:
            transport.container_flag = True

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

        return financial

    def _parse_valuation(self) -> Valuation:
        """Parse les informations de valorisation globale"""
        valuation = Valuation()

        valuation.calculation_mode = '2'

        # Poids net total
        net_weight = self._extract_field(r'11\.\s*Poids Total NET.*?(\d[\d\s,\.]+)')
        if net_weight:
            valuation.total_weight = self._parse_number(net_weight)

        # Poids brut total
        gross_weight = self._extract_field(r'12\.\s*Poids Total BRUT.*?(\d[\d\s,\.]+)')
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

        # CIF
        cif = self._extract_field(r'23\.\s*Valeur CIF Attestée[:\s]+([\d\s,\.]+)')

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
        # Utilise la valeur CIF totale
        cif = self._extract_field(r'23\.\s*Valeur CIF Attestée[:\s]+([\d\s,\.]+)')
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
