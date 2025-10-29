"""
Module de génération XML ASYCUDA
Crée des fichiers XML conformes au format ASYCUDA à partir des données RFCV
"""
import xml.etree.ElementTree as ET
from xml.dom import minidom
from typing import Optional, List
from datetime import datetime
from models import RFCVData, Item, Trader, CurrencyAmount


class XMLGenerator:
    """Générateur de fichiers XML ASYCUDA"""

    def __init__(self, rfcv_data: RFCVData):
        """
        Initialise le générateur avec les données RFCV

        Args:
            rfcv_data: Données RFCV parsées
        """
        self.data = rfcv_data
        self.root = None

    def _convert_date_to_asycuda_format(self, date_str: Optional[str]) -> Optional[str]:
        """
        Convertit une date du format DD/MM/YYYY au format ASYCUDA M/D/YY

        Args:
            date_str: Date au format DD/MM/YYYY (ex: "26/09/2025")

        Returns:
            Date au format M/D/YY (ex: "9/26/25") ou None si conversion impossible

        Examples:
            "26/09/2025" -> "9/26/25"
            "01/12/2025" -> "12/1/25"
            "10/07/2025" -> "7/10/25"
        """
        if not date_str:
            return None

        try:
            # Parse DD/MM/YYYY
            dt = datetime.strptime(date_str, '%d/%m/%Y')
            # Format as M/D/YY (sans zéros initiaux)
            return f"{dt.month}/{dt.day}/{dt.year % 100}"
        except (ValueError, AttributeError):
            # Si le format est déjà M/D/YY ou invalide, retourner tel quel
            return date_str

    def generate(self) -> ET.Element:
        """
        Génère l'arbre XML complet

        Returns:
            Element racine de l'arbre XML
        """
        self.root = ET.Element('ASYCUDA')

        # Construire toutes les sections
        self._build_export_release()
        self._build_assessment_notice()
        self._build_global_taxes()
        self._build_property()
        self._build_identification()
        self._build_traders()
        self._build_declarant()
        self._build_general_information()
        self._build_transport()
        self._build_financial()
        self._build_warehouse()
        self._build_transit()
        self._build_valuation()
        self._build_containers()
        self._build_prev_decl()
        self._build_items()

        return self.root

    def save(self, output_path: str, pretty_print: bool = True):
        """
        Sauvegarde le XML dans un fichier

        Args:
            output_path: Chemin du fichier de sortie
            pretty_print: Formater le XML avec indentation
        """
        if self.root is None:
            self.generate()

        if pretty_print:
            xml_str = self._prettify(self.root)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(xml_str)
        else:
            tree = ET.ElementTree(self.root)
            tree.write(output_path, encoding='utf-8', xml_declaration=True)

    def _add_element(self, parent: ET.Element, tag: str, text: Optional[str] = None) -> ET.Element:
        """
        Ajoute un élément avec gestion de <null/>

        Args:
            parent: Element parent
            tag: Nom du tag
            text: Texte de l'élément (None pour <null/>)

        Returns:
            Element créé
        """
        elem = ET.SubElement(parent, tag)
        if text is not None and str(text).strip():
            elem.text = str(text)
        else:
            null_elem = ET.SubElement(elem, 'null')
        return elem

    def _add_simple_element(self, parent: ET.Element, tag: str, text: Optional[str] = None) -> ET.Element:
        """
        Ajoute un élément simple (vide si None, pas de <null/>)

        Args:
            parent: Element parent
            tag: Nom du tag
            text: Texte de l'élément

        Returns:
            Element créé
        """
        elem = ET.SubElement(parent, tag)
        if text is not None and str(text).strip():
            elem.text = str(text)
        return elem

    def _build_export_release(self):
        """Construit la section Export_release"""
        export_rel = ET.SubElement(self.root, 'Export_release')
        self._add_simple_element(export_rel, 'Date_of_exit')
        self._add_simple_element(export_rel, 'Time_of_exit')
        self._add_element(export_rel, 'Actual_office_of_exit_code')
        self._add_element(export_rel, 'Actual_office_of_exit_name')
        self._add_element(export_rel, 'Exit_reference')
        self._add_element(export_rel, 'Comments')

    def _build_assessment_notice(self):
        """Construit la section Assessment_notice"""
        assessment = ET.SubElement(self.root, 'Assessment_notice')
        # 14 Item_tax_total vides
        for _ in range(14):
            self._add_simple_element(assessment, 'Item_tax_total')

    def _build_global_taxes(self):
        """Construit la section Global_taxes"""
        global_taxes = ET.SubElement(self.root, 'Global_taxes')
        # 8 Global_tax_item vides
        for _ in range(8):
            self._add_simple_element(global_taxes, 'Global_tax_item')

    def _build_property(self):
        """Construit la section Property"""
        prop_elem = ET.SubElement(self.root, 'Property')
        prop = self.data.property

        self._add_simple_element(prop_elem, 'Sad_flow', prop.sad_flow if prop else 'I')

        forms = ET.SubElement(prop_elem, 'Forms')
        self._add_simple_element(forms, 'Number_of_the_form', str(prop.form_number) if prop and prop.form_number else '1')
        self._add_simple_element(forms, 'Total_number_of_forms', str(prop.total_forms) if prop and prop.total_forms else '1')

        nbers = ET.SubElement(prop_elem, 'Nbers')
        self._add_simple_element(nbers, 'Number_of_loading_lists')
        self._add_simple_element(nbers, 'Total_number_of_items', str(len(self.data.items)) if self.data.items else '0')
        self._add_simple_element(nbers, 'Total_number_of_packages', str(prop.total_packages) if prop and prop.total_packages else '0')

        # P3.6: Ajouter le type de colisage
        if prop and prop.package_type:
            self._add_simple_element(nbers, 'Package_type', prop.package_type)

        self._add_element(prop_elem, 'Place_of_declaration')
        self._add_simple_element(prop_elem, 'Date_of_declaration', prop.date_of_declaration if prop and prop.date_of_declaration else '')
        self._add_simple_element(prop_elem, 'Selected_page', str(prop.selected_page) if prop and prop.selected_page else '1')

    def _build_identification(self):
        """Construit la section Identification"""
        ident_elem = ET.SubElement(self.root, 'Identification')
        ident = self.data.identification

        office_seg = ET.SubElement(ident_elem, 'Office_segment')
        self._add_simple_element(office_seg, 'Customs_clearance_office_code', ident.customs_office_code if ident else 'CIAB1')
        self._add_simple_element(office_seg, 'Customs_Clearance_office_name', ident.customs_office_name if ident else 'ABIDJAN-PORT')

        type_elem = ET.SubElement(ident_elem, 'Type')
        self._add_simple_element(type_elem, 'Type_of_declaration', ident.type_of_declaration if ident else 'IM')
        self._add_simple_element(type_elem, 'Declaration_gen_procedure_code', ident.declaration_procedure_code if ident else '4')
        self._add_element(type_elem, 'Type_of_transit_document')

        self._add_simple_element(ident_elem, 'Manifest_reference_number', ident.manifest_reference if ident else '')

        # P3.5: Ajouter les nouveaux champs PRIORITÉ 3
        # Date RFCV (section 5)
        if ident and ident.rfcv_date:
            self._add_simple_element(ident_elem, 'RFCV_date', self._convert_date_to_asycuda_format(ident.rfcv_date))

        # No. FDI/DAI (section 7)
        if ident and ident.fdi_number:
            self._add_simple_element(ident_elem, 'FDI_number', ident.fdi_number)

        # Date FDI/DAI (section 8)
        if ident and ident.fdi_date:
            self._add_simple_element(ident_elem, 'FDI_date', self._convert_date_to_asycuda_format(ident.fdi_date))

        # Type de livraison (section 6: TOT/PART)
        if ident and ident.delivery_type:
            self._add_simple_element(ident_elem, 'Delivery_type', ident.delivery_type)

        registration = ET.SubElement(ident_elem, 'Registration')
        self._add_element(registration, 'Serial_number')
        self._add_simple_element(registration, 'Number', ident.registration_number if ident and ident.registration_number else '')
        self._add_simple_element(registration, 'Date', self._convert_date_to_asycuda_format(ident.registration_date) if ident and ident.registration_date else '')

        assessment = ET.SubElement(ident_elem, 'Assessment')
        self._add_element(assessment, 'Serial_number')
        self._add_simple_element(assessment, 'Number', ident.assessment_number if ident and ident.assessment_number else '')
        self._add_simple_element(assessment, 'Date', self._convert_date_to_asycuda_format(ident.assessment_date) if ident and ident.assessment_date else '')

        receipt = ET.SubElement(ident_elem, 'receipt')
        self._add_element(receipt, 'Serial_number')
        self._add_simple_element(receipt, 'Number')
        self._add_simple_element(receipt, 'Date')

    def _build_traders(self):
        """Construit la section Traders"""
        traders = ET.SubElement(self.root, 'Traders')

        # Exportateur
        exporter_elem = ET.SubElement(traders, 'Exporter')
        exp = self.data.exporter
        self._add_simple_element(exporter_elem, 'Exporter_code', exp.code if exp and exp.code else '')
        exporter_name = f"{exp.name}\n{exp.address}" if exp and exp.name else ""
        self._add_simple_element(exporter_elem, 'Exporter_name', exporter_name)

        # Destinataire
        consignee_elem = ET.SubElement(traders, 'Consignee')
        cons = self.data.consignee
        self._add_simple_element(consignee_elem, 'Consignee_code', cons.code if cons and cons.code else '')
        consignee_name = f"{cons.name}\n{cons.address}" if cons and cons.name else ""
        self._add_simple_element(consignee_elem, 'Consignee_name', consignee_name)

        # Financial
        financial_elem = ET.SubElement(traders, 'Financial')
        self._add_element(financial_elem, 'Financial_code')
        self._add_element(financial_elem, 'Financial_name')

    def _build_declarant(self):
        """Construit la section Declarant"""
        declarant_elem = ET.SubElement(self.root, 'Declarant')
        decl = self.data.declarant

        self._add_simple_element(declarant_elem, 'Declarant_code', decl.code if decl and decl.code else '')
        declarant_name = f"{decl.name}\n{decl.address}" if decl and decl.name else ""
        self._add_simple_element(declarant_elem, 'Declarant_name', declarant_name)
        self._add_simple_element(declarant_elem, 'Declarant_representative', decl.representative if decl and decl.representative else '')

        reference = ET.SubElement(declarant_elem, 'Reference')
        self._add_simple_element(reference, 'Number', decl.reference if decl and decl.reference else '')

    def _build_general_information(self):
        """Construit la section General_information"""
        gen_info = ET.SubElement(self.root, 'General_information')
        country_data = self.data.country

        country_elem = ET.SubElement(gen_info, 'Country')
        self._add_simple_element(country_elem, 'Country_first_destination', country_data.first_destination if country_data else 'CN')
        self._add_simple_element(country_elem, 'Trading_country')

        export_elem = ET.SubElement(country_elem, 'Export')
        self._add_simple_element(export_elem, 'Export_country_code', country_data.export_country_code if country_data else 'CN')
        self._add_simple_element(export_elem, 'Export_country_name', country_data.export_country_name if country_data else 'Chine')
        self._add_simple_element(export_elem, 'Export_country_region')

        destination_elem = ET.SubElement(country_elem, 'Destination')
        self._add_simple_element(destination_elem, 'Destination_country_code', country_data.destination_country_code if country_data else 'CI')
        self._add_simple_element(destination_elem, 'Destination_country_name', country_data.destination_country_name if country_data else "Cote d'Ivoire")
        self._add_simple_element(destination_elem, 'Destination_country_region')

        self._add_simple_element(country_elem, 'Country_of_origin_name', country_data.origin_country_name if country_data else 'Chine')

        self._add_simple_element(gen_info, 'Value_details', str(self.data.value_details) if self.data.value_details else '')
        self._add_element(gen_info, 'CAP')
        self._add_element(gen_info, 'Additional_information')
        self._add_element(gen_info, 'Comments_free_text')

    def _build_transport(self):
        """Construit la section Transport"""
        transport_elem = ET.SubElement(self.root, 'Transport')
        trans = self.data.transport

        means = ET.SubElement(transport_elem, 'Means_of_transport')

        departure = ET.SubElement(means, 'Departure_arrival_information')
        # Identity: Nom du navire SANS date (conforme ASYCUDA)
        vessel_id = trans.vessel_name if trans and trans.vessel_name else ''
        self._add_simple_element(departure, 'Identity', vessel_id)
        self._add_simple_element(departure, 'Nationality', trans.vessel_nationality if trans and trans.vessel_nationality else '')

        border = ET.SubElement(means, 'Border_information')
        # Identity: Nom du navire SANS date (conforme ASYCUDA)
        self._add_simple_element(border, 'Identity', vessel_id)
        self._add_element(border, 'Nationality')  # <null/> format pour conformité ASYCUDA
        self._add_simple_element(border, 'Mode', trans.border_mode if trans and trans.border_mode else '1')

        self._add_element(means, 'Inland_mode_of_transport')

        # Note: Bill of Lading n'est PAS dans Transport/Means_of_transport dans ASYCUDA
        # Il va dans Item/Previous_doc/Summary_declaration (voir _add_item_previous_doc)

        self._add_simple_element(transport_elem, 'Container_flag', 'true' if trans and trans.container_flag else 'false')

        delivery = ET.SubElement(transport_elem, 'Delivery_terms')
        # P1.3: Utiliser incoterm si disponible
        incoterm_code = trans.incoterm if trans and trans.incoterm else (trans.delivery_terms_code if trans and trans.delivery_terms_code else 'CFR')
        self._add_simple_element(delivery, 'Code', incoterm_code)
        self._add_element(delivery, 'Place')
        self._add_simple_element(delivery, 'Situation')

        border_office = ET.SubElement(transport_elem, 'Border_office')
        self._add_simple_element(border_office, 'Code', trans.border_office_code if trans else 'CIAB1')
        self._add_simple_element(border_office, 'Name', trans.border_office_name if trans else 'ABIDJAN-PORT')

        loading = ET.SubElement(transport_elem, 'Place_of_loading')
        # P1.6: Utiliser loading_location si disponible
        loading_code = trans.loading_location if trans and trans.loading_location else (trans.loading_place_code if trans and trans.loading_place_code else '')
        self._add_simple_element(loading, 'Code', loading_code)
        self._add_simple_element(loading, 'Name', trans.loading_place_name if trans and trans.loading_place_name else '')
        self._add_element(loading, 'Country')

        # P1.6: Utiliser discharge_location si disponible
        discharge = trans.discharge_location if trans and trans.discharge_location else (trans.location_of_goods if trans and trans.location_of_goods else 'AIRE')
        self._add_simple_element(transport_elem, 'Location_of_goods', discharge)

    def _build_financial(self):
        """Construit la section Financial"""
        financial_elem = ET.SubElement(self.root, 'Financial')
        fin = self.data.financial

        transaction = ET.SubElement(financial_elem, 'Financial_transaction')
        self._add_simple_element(transaction, 'code1', fin.transaction_code1 if fin else '0')
        self._add_simple_element(transaction, 'code2', fin.transaction_code2 if fin else '1')

        bank_elem = ET.SubElement(financial_elem, 'Bank')
        bank = fin.bank if fin else None
        self._add_simple_element(bank_elem, 'Code', bank.code if bank and bank.code else '')
        self._add_simple_element(bank_elem, 'Name', bank.name if bank and bank.name else '')
        self._add_simple_element(bank_elem, 'Branch', bank.branch if bank and bank.branch else '')
        self._add_element(bank_elem, 'Reference', bank.reference if bank and bank.reference else None)

        terms = ET.SubElement(financial_elem, 'Terms')
        self._add_element(terms, 'Code')
        self._add_element(terms, 'Description')

        # P2.5: Ajouter les données de facture
        # Total_invoice: Valeur de la facture (section 18 dans RFCV, non utilisée - utilise FOB section 19 à la place)
        self._add_element(financial_elem, 'Total_invoice', str(fin.invoice_amount) if fin and fin.invoice_amount else None)

        # P2.5: Ajouter numéro et date de facture
        if fin and fin.invoice_number:
            self._add_simple_element(financial_elem, 'Invoice_number', fin.invoice_number)
        if fin and fin.invoice_date:
            self._add_simple_element(financial_elem, 'Invoice_date', self._convert_date_to_asycuda_format(fin.invoice_date))

        self._add_simple_element(financial_elem, 'Deffered_payment_reference', fin.deferred_payment_ref if fin and fin.deferred_payment_ref else '')
        self._add_simple_element(financial_elem, 'Mode_of_payment', fin.mode_of_payment if fin and fin.mode_of_payment else 'COMPTE DE PAIEMENT')

        amounts = ET.SubElement(financial_elem, 'Amounts')
        self._add_simple_element(amounts, 'Total_manual_taxes')
        self._add_simple_element(amounts, 'Global_taxes')
        self._add_simple_element(amounts, 'Totals_taxes')

        guarantee = ET.SubElement(financial_elem, 'Guarantee')
        self._add_element(guarantee, 'Name')
        self._add_simple_element(guarantee, 'Amount')
        self._add_simple_element(guarantee, 'Date')
        excluded = ET.SubElement(guarantee, 'Excluded_country')
        self._add_element(excluded, 'Code')
        self._add_element(excluded, 'Name')

    def _build_warehouse(self):
        """Construit la section Warehouse"""
        warehouse = ET.SubElement(self.root, 'Warehouse')
        self._add_simple_element(warehouse, 'Identification')
        self._add_simple_element(warehouse, 'Delay')

    def _build_transit(self):
        """Construit la section Transit"""
        transit = ET.SubElement(self.root, 'Transit')

        principal = ET.SubElement(transit, 'Principal')
        self._add_element(principal, 'Code')
        self._add_element(principal, 'Name')
        self._add_element(principal, 'Representative')

        signature = ET.SubElement(transit, 'Signature')
        self._add_element(signature, 'Place')
        self._add_simple_element(signature, 'Date')

        destination = ET.SubElement(transit, 'Destination')
        self._add_element(destination, 'Office')
        self._add_element(destination, 'Country')

        seals = ET.SubElement(transit, 'Seals')
        self._add_simple_element(seals, 'Number')
        self._add_element(seals, 'Identity')

        self._add_simple_element(transit, 'Result_of_control')
        self._add_simple_element(transit, 'Time_limit')
        self._add_element(transit, 'Officer_name')

    def _build_valuation(self):
        """Construit la section Valuation"""
        valuation_elem = ET.SubElement(self.root, 'Valuation')
        val = self.data.valuation

        self._add_simple_element(valuation_elem, 'Calculation_working_mode', val.calculation_mode if val else '2')

        weight = ET.SubElement(valuation_elem, 'Weight')
        # Gross_weight à null - ASYCUDA calcule automatiquement depuis les Gross_weight_itm des articles
        self._add_simple_element(weight, 'Gross_weight', '')
        # Net_weight à null - ASYCUDA calcule automatiquement depuis les Net_weight_itm des articles
        self._add_simple_element(weight, 'Net_weight', '')

        self._add_simple_element(valuation_elem, 'Total_cost', str(val.total_cost) if val and val.total_cost else '')
        self._add_simple_element(valuation_elem, 'Total_CIF', str(val.total_cif) if val and val.total_cif else '')

        # Currency amounts
        # Gs_Invoice: Utilise section 19 (Total Valeur FOB attestée) - valeur de la facture commerciale
        self._add_currency_amount(valuation_elem, 'Gs_Invoice', val.invoice if val else None, allow_null=True)
        # Gs_external_freight à null - ASYCUDA calcule automatiquement depuis les item_external_freight des articles
        self._add_currency_amount(valuation_elem, 'Gs_external_freight', None, allow_null=True)
        self._add_currency_amount(valuation_elem, 'Gs_internal_freight', val.internal_freight if val else None)
        # Gs_insurance à null - ASYCUDA calcule automatiquement depuis les item_insurance des articles
        self._add_currency_amount(valuation_elem, 'Gs_insurance', None, allow_null=True)
        self._add_currency_amount(valuation_elem, 'Gs_other_cost', val.other_cost if val else None)
        self._add_currency_amount(valuation_elem, 'Gs_deduction', val.deduction if val else None)

        total = ET.SubElement(valuation_elem, 'Total')
        # Total_invoice: Valeur FOB totale (section 19) en devise étrangère
        self._add_element(total, 'Total_invoice', str(val.total_invoice) if val and val.total_invoice else None)
        self._add_simple_element(total, 'Total_weight', str(val.total_weight) if val and val.total_weight else '')

    def _add_currency_amount(self, parent: ET.Element, tag: str, currency: Optional[CurrencyAmount], allow_null: bool = False):
        """Ajoute un élément de type montant avec devise

        P2.6: Si currency est None:
        - Si allow_null=True: crée <null/> uniquement (pour external_freight)
        - Si allow_null=False: utilise les données de Financial (currency_code, exchange_rate)

        Args:
            parent: Element parent
            tag: Nom du tag
            currency: Objet CurrencyAmount ou None
            allow_null: Si True, crée <null/> quand currency est None
        """
        elem = ET.SubElement(parent, tag)

        if currency:
            self._add_simple_element(elem, 'Amount_national_currency', str(currency.amount_national) if currency.amount_national else '0.0')
            self._add_simple_element(elem, 'Amount_foreign_currency', str(currency.amount_foreign) if currency.amount_foreign else '0.0')
            self._add_element(elem, 'Currency_code', currency.currency_code)
            self._add_simple_element(elem, 'Currency_name', currency.currency_name if currency.currency_name else 'Pas de devise étrangère')
            # Format avec 4 décimales pour conformité ASYCUDA (ex: 566.6700)
            rate_str = f'{currency.currency_rate:.4f}' if currency.currency_rate else '0.0'
            self._add_simple_element(elem, 'Currency_rate', rate_str)
        elif allow_null:
            # Créer un seul <null/> au lieu de remplir avec des valeurs par défaut
            ET.SubElement(elem, 'null')
        else:
            # P2.6: Utiliser les données financières si disponibles
            fin = self.data.financial
            currency_code = fin.currency_code if fin and fin.currency_code else None
            # Format avec 4 décimales pour conformité ASYCUDA
            exchange_rate = f'{fin.exchange_rate:.4f}' if fin and fin.exchange_rate else '0.0'

            self._add_simple_element(elem, 'Amount_national_currency', '0.0')
            self._add_simple_element(elem, 'Amount_foreign_currency', '0.0')
            self._add_element(elem, 'Currency_code', currency_code)
            self._add_simple_element(elem, 'Currency_name', 'Pas de devise étrangère')
            self._add_simple_element(elem, 'Currency_rate', exchange_rate)

    def _build_containers(self):
        """Construit la section Container"""
        for container in self.data.containers:
            container_elem = ET.SubElement(self.root, 'Container')
            self._add_simple_element(container_elem, 'Item_Number', str(container.item_number) if container.item_number else '1')
            self._add_simple_element(container_elem, 'Container_identity', container.identity if container.identity else '')
            self._add_simple_element(container_elem, 'Container_type', container.container_type if container.container_type else '40HC')
            self._add_simple_element(container_elem, 'Empty_full_indicator', container.empty_full_indicator if container.empty_full_indicator else '1/1')
            self._add_simple_element(container_elem, 'Gross_weight', str(container.gross_weight) if container.gross_weight else '')
            self._add_element(container_elem, 'Goods_description')
            self._add_element(container_elem, 'Packages_type')
            self._add_simple_element(container_elem, 'Packages_number', str(container.packages_number) if container.packages_number else '')
            self._add_simple_element(container_elem, 'Packages_weight', str(container.packages_weight) if container.packages_weight else '')

    def _build_prev_decl(self):
        """Construit la section Prev_decl"""
        prev_decl = ET.SubElement(self.root, 'Prev_decl')
        self._add_element(prev_decl, 'Prev_decl_office_code')
        self._add_simple_element(prev_decl, 'Prev_decl_reg_year')
        self._add_element(prev_decl, 'Prev_decl_reg_serial')
        self._add_simple_element(prev_decl, 'Prev_decl_reg_number')
        self._add_simple_element(prev_decl, 'Prev_decl_item_number')
        self._add_element(prev_decl, 'Prev_decl_HS_code')
        self._add_element(prev_decl, 'Prev_decl_HS_prec')
        self._add_element(prev_decl, 'Prev_decl_country_origin')
        self._add_simple_element(prev_decl, 'Prev_decl_number_packages')
        self._add_simple_element(prev_decl, 'Prev_decl_weight')
        self._add_simple_element(prev_decl, 'Prev_decl_supp_quantity')
        self._add_simple_element(prev_decl, 'Prev_decl_ref_value')
        self._add_simple_element(prev_decl, 'Prev_decl_current_item')
        self._add_simple_element(prev_decl, 'Prev_decl_number_packages_written_off')
        self._add_simple_element(prev_decl, 'Prev_decl_weight_written_off')
        self._add_simple_element(prev_decl, 'Prev_decl_supp_quantity_written_off')
        self._add_simple_element(prev_decl, 'Prev_decl_ref_value_written_off')

    def _build_items(self):
        """Construit les sections Item"""
        for item in self.data.items:
            self._build_item(item)

    def _build_item(self, item: Item):
        """Construit une section Item complète"""
        item_elem = ET.SubElement(self.root, 'Item')

        # Documents attachés
        for doc in item.attached_documents:
            doc_elem = ET.SubElement(item_elem, 'Attached_documents')
            self._add_simple_element(doc_elem, 'Attached_document_code', doc.code if doc.code else '')
            self._add_simple_element(doc_elem, 'Attached_document_name', doc.name if doc.name else '')
            self._add_simple_element(doc_elem, 'Attached_document_reference', doc.reference if doc.reference else '')
            self._add_simple_element(doc_elem, 'Attached_document_from_rule', str(doc.from_rule) if doc.from_rule else '')
            if doc.document_date:
                self._add_simple_element(doc_elem, 'Attached_document_date', self._convert_date_to_asycuda_format(doc.document_date))

        # Document châssis (code 6122) si présent
        if item.packages and item.packages.chassis_number:
            chassis_doc_elem = ET.SubElement(item_elem, 'Attached_documents')
            self._add_simple_element(chassis_doc_elem, 'Attached_document_code', '6122')
            self._add_simple_element(chassis_doc_elem, 'Attached_document_name', 'CHASSIS MOTOS')
            self._add_simple_element(chassis_doc_elem, 'Attached_document_reference', item.packages.chassis_number)
            self._add_simple_element(chassis_doc_elem, 'Attached_document_from_rule', '1')

        # Packages
        if item.packages:
            packages = ET.SubElement(item_elem, 'Packages')
            pkg = item.packages
            self._add_simple_element(packages, 'Number_of_packages', str(pkg.number_of_packages) if pkg.number_of_packages else '')
            self._add_simple_element(packages, 'Marks1_of_packages', pkg.marks1 if pkg.marks1 else '')
            self._add_element(packages, 'Marks2_of_packages', pkg.marks2)
            self._add_simple_element(packages, 'Kind_of_packages_code', pkg.kind_code if pkg.kind_code else 'PK')
            self._add_simple_element(packages, 'Kind_of_packages_name', pkg.kind_name if pkg.kind_name else 'Colis ("package")')

        # IncoTerms
        incoterms = ET.SubElement(item_elem, 'IncoTerms')
        self._add_simple_element(incoterms, 'Code', item.incoterms_code if item.incoterms_code else 'CFR')
        self._add_element(incoterms, 'Place')

        # Tarification
        if item.tarification:
            tarif_elem = ET.SubElement(item_elem, 'Tarification')
            tarif = item.tarification

            self._add_element(tarif_elem, 'Tarification_data')

            if tarif.hscode:
                hscode_elem = ET.SubElement(tarif_elem, 'HScode')
                self._add_simple_element(hscode_elem, 'Commodity_code', tarif.hscode.commodity_code if tarif.hscode.commodity_code else '')
                self._add_simple_element(hscode_elem, 'Precision_1', tarif.hscode.precision_1 if tarif.hscode.precision_1 else '00')
                self._add_element(hscode_elem, 'Precision_2', tarif.hscode.precision_2)
                self._add_element(hscode_elem, 'Precision_3', tarif.hscode.precision_3)
                self._add_element(hscode_elem, 'Precision_4', tarif.hscode.precision_4)

            self._add_element(tarif_elem, 'Preference_code')
            self._add_simple_element(tarif_elem, 'Extended_customs_procedure', tarif.extended_procedure if tarif.extended_procedure else '4000')
            self._add_simple_element(tarif_elem, 'National_customs_procedure', tarif.national_procedure if tarif.national_procedure else '000')
            self._add_element(tarif_elem, 'Quota_code')

            quota = ET.SubElement(tarif_elem, 'Quota')
            self._add_element(quota, 'QuotaCode')
            self._add_element(quota, 'QuotaId')
            quota_item = ET.SubElement(quota, 'QuotaItem')
            self._add_element(quota_item, 'ItmNbr')

            # Supplementary units (3 blocs)
            for i, unit in enumerate(tarif.supplementary_units[:3] if tarif.supplementary_units else []):
                supp_unit = ET.SubElement(tarif_elem, 'Supplementary_unit')
                self._add_simple_element(supp_unit, 'Suppplementary_unit_code', unit.code if unit and unit.code else '')
                self._add_simple_element(supp_unit, 'Suppplementary_unit_name', unit.name if unit and unit.name else '')
                self._add_simple_element(supp_unit, 'Suppplementary_unit_quantity', str(unit.quantity) if unit and unit.quantity else '')

            # Remplir le reste avec des unités vides
            for _ in range(len(tarif.supplementary_units) if tarif.supplementary_units else 0, 3):
                supp_unit = ET.SubElement(tarif_elem, 'Supplementary_unit')
                self._add_element(supp_unit, 'Suppplementary_unit_code')
                self._add_simple_element(supp_unit, 'Suppplementary_unit_name')
                self._add_simple_element(supp_unit, 'Suppplementary_unit_quantity')

            self._add_simple_element(tarif_elem, 'Item_price', str(tarif.item_price) if tarif.item_price else '')
            self._add_simple_element(tarif_elem, 'Valuation_method_code', tarif.valuation_method if tarif.valuation_method else '02')
            self._add_simple_element(tarif_elem, 'Value_item', '')
            self._add_element(tarif_elem, 'Attached_doc_item')
            self._add_element(tarif_elem, 'A.I._code')

        # Goods description
        goods_desc = ET.SubElement(item_elem, 'Goods_description')
        self._add_simple_element(goods_desc, 'Country_of_origin_code', item.country_of_origin_code if item.country_of_origin_code else 'CN')
        self._add_element(goods_desc, 'Country_of_origin_region')
        self._add_simple_element(goods_desc, 'Description_of_goods', item.goods_description if item.goods_description else '')
        self._add_element(goods_desc, 'Commercial_Description', item.commercial_description)

        # Previous doc
        prev_doc = ET.SubElement(item_elem, 'Previous_doc')
        self._add_simple_element(prev_doc, 'Summary_declaration', item.summary_declaration if item.summary_declaration else '')
        self._add_element(prev_doc, 'Summary_declaration_sl')
        self._add_simple_element(prev_doc, 'Previous_document_reference', item.previous_document_reference if item.previous_document_reference else '')
        self._add_element(prev_doc, 'Previous_warehouse_code')

        self._add_simple_element(item_elem, 'Licence_number')
        self._add_simple_element(item_elem, 'Amount_deducted_from_licence')
        self._add_simple_element(item_elem, 'Quantity_deducted_from_licence')
        self._add_simple_element(item_elem, 'Free_text_1', item.free_text_1 if item.free_text_1 else '')
        self._add_simple_element(item_elem, 'Free_text_2', item.free_text_2 if item.free_text_2 else '')

        # Taxation
        if item.taxation:
            taxation_elem = ET.SubElement(item_elem, 'Taxation')
            tax = item.taxation

            self._add_simple_element(taxation_elem, 'Item_taxes_amount', str(tax.item_taxes_amount) if tax.item_taxes_amount is not None else '')
            self._add_simple_element(taxation_elem, 'Item_taxes_guaranted_amount', str(tax.item_taxes_guaranteed) if tax.item_taxes_guaranteed is not None else '0.0')
            self._add_element(taxation_elem, 'Item_taxes_mode_of_payment')
            self._add_simple_element(taxation_elem, 'Counter_of_normal_mode_of_payment')
            self._add_simple_element(taxation_elem, 'Displayed_item_taxes_amount')

            # 8 Taxation lines
            for i in range(8):
                tax_line_elem = ET.SubElement(taxation_elem, 'Taxation_line')
                if i < len(tax.taxation_lines):
                    line = tax.taxation_lines[i]
                    self._add_element(tax_line_elem, 'Duty_tax_code', line.duty_tax_code)
                    self._add_simple_element(tax_line_elem, 'Duty_tax_Base', str(line.duty_tax_base) if line.duty_tax_base else '')
                    self._add_simple_element(tax_line_elem, 'Duty_tax_rate', str(line.duty_tax_rate) if line.duty_tax_rate else '')
                    self._add_simple_element(tax_line_elem, 'Duty_tax_amount', str(line.duty_tax_amount) if line.duty_tax_amount else '')
                    self._add_element(tax_line_elem, 'Duty_tax_MP', line.duty_tax_mp)
                    self._add_element(tax_line_elem, 'Duty_tax_Type_of_calculation', line.duty_tax_calculation_type)
                else:
                    self._add_element(tax_line_elem, 'Duty_tax_code')
                    self._add_simple_element(tax_line_elem, 'Duty_tax_Base')
                    self._add_simple_element(tax_line_elem, 'Duty_tax_rate')
                    self._add_simple_element(tax_line_elem, 'Duty_tax_amount')
                    self._add_element(tax_line_elem, 'Duty_tax_MP')
                    self._add_element(tax_line_elem, 'Duty_tax_Type_of_calculation')

        # Valuation_item
        if item.valuation_item:
            val_item_elem = ET.SubElement(item_elem, 'Valuation_item')
            val_item = item.valuation_item

            weight = ET.SubElement(val_item_elem, 'Weight_itm')
            self._add_simple_element(weight, 'Gross_weight_itm', str(val_item.gross_weight) if val_item.gross_weight else '')
            self._add_simple_element(weight, 'Net_weight_itm', str(val_item.net_weight) if val_item.net_weight else '')

            self._add_simple_element(val_item_elem, 'Total_cost_itm', str(val_item.total_cost) if val_item.total_cost else '')
            self._add_simple_element(val_item_elem, 'Total_CIF_itm', str(val_item.total_cif) if val_item.total_cif else '')
            self._add_simple_element(val_item_elem, 'Rate_of_adjustement', str(val_item.rate_of_adjustment) if val_item.rate_of_adjustment else '0')
            self._add_simple_element(val_item_elem, 'Statistical_value', str(val_item.statistical_value) if val_item.statistical_value else '')
            self._add_simple_element(val_item_elem, 'Alpha_coeficient_of_apportionment')

            # Currency amounts pour item
            self._add_currency_amount(val_item_elem, 'Item_Invoice', val_item.invoice)
            # item_external_freight à null - sections 18 et 20 du RFCV non utilisées par ASYCUDA
            self._add_currency_amount(val_item_elem, 'item_external_freight', val_item.external_freight, allow_null=True)
            self._add_currency_amount(val_item_elem, 'item_internal_freight', val_item.internal_freight)
            self._add_currency_amount(val_item_elem, 'item_insurance', val_item.insurance, allow_null=True)
            self._add_currency_amount(val_item_elem, 'item_other_cost', val_item.other_cost)
            self._add_currency_amount(val_item_elem, 'item_deduction', val_item.deduction)

            market = ET.SubElement(val_item_elem, 'Market_valuer')
            self._add_simple_element(market, 'Rate')
            self._add_element(market, 'Currency_code')
            self._add_simple_element(market, 'Currency_amount', '0.0')
            self._add_element(market, 'Basis_description')
            self._add_simple_element(market, 'Basis_amount')

    def _prettify(self, elem: ET.Element) -> str:
        """
        Formate le XML avec indentation

        Args:
            elem: Element racine

        Returns:
            XML formaté avec indentation
        """
        rough_string = ET.tostring(elem, encoding='utf-8')
        reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent="  ", encoding='utf-8').decode('utf-8')


def generate_xml(rfcv_data: RFCVData, output_path: str):
    """
    Fonction utilitaire pour générer un XML ASYCUDA

    Args:
        rfcv_data: Données RFCV
        output_path: Chemin de sortie
    """
    generator = XMLGenerator(rfcv_data)
    generator.generate()
    generator.save(output_path, pretty_print=True)
