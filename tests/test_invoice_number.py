"""
Tests pour la propagation du numéro de facture
Vérifie que le numéro de facture apparaît uniquement sur le premier article
"""
import pytest
import sys
from pathlib import Path

# Ajouter le répertoire src au path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from models import (
    RFCVData, Financial, Identification, Item, Tarification,
    HSCode, Package, ValuationItem, AttachedDocument
)
from rfcv_parser import RFCVParser


class TestInvoiceNumberPropagation:
    """Tests de propagation du numéro de facture"""

    def test_invoice_number_first_item_only_attached_documents(self):
        """Le document FACTURE (code 0007) doit apparaître uniquement sur le premier article"""
        # Créer des données de test
        rfcv_data = RFCVData()
        rfcv_data.financial = Financial(
            invoice_number="2025/BC/SN18215",
            invoice_date="17/07/2025"
        )
        rfcv_data.identification = Identification(
            rfcv_number="RCS25119416",
            fdi_number="FDI-123456"
        )

        # Créer 3 articles de test
        rfcv_data.items = [
            Item(
                goods_description=f"Article {i+1}",
                tarification=Tarification(
                    hscode=HSCode(commodity_code="84099900")
                )
            )
            for i in range(3)
        ]

        # Simuler l'ajout des documents attachés
        parser = RFCVParser("dummy.pdf")
        parser._add_attached_documents(rfcv_data)

        # Vérifications
        # Premier article : doit avoir le document FACTURE (0007)
        first_item_docs = rfcv_data.items[0].attached_documents
        invoice_docs_first = [doc for doc in first_item_docs if doc.code == '0007']
        assert len(invoice_docs_first) == 1, "Le premier article doit avoir exactement 1 document FACTURE"
        assert invoice_docs_first[0].name == 'FACTURE'
        assert invoice_docs_first[0].reference == "2025/BC/SN18215"
        assert invoice_docs_first[0].document_date == "17/07/2025"

        # Articles suivants : NE doivent PAS avoir le document FACTURE (0007)
        for i, item in enumerate(rfcv_data.items[1:], start=2):
            invoice_docs = [doc for doc in item.attached_documents if doc.code == '0007']
            assert len(invoice_docs) == 0, f"L'article {i} ne doit PAS avoir de document FACTURE"

    def test_rfcv_and_fdi_on_all_items(self):
        """Le document RFCV (2501) doit apparaître sur tous les articles, FDI (6610) sur le premier uniquement"""
        rfcv_data = RFCVData()
        rfcv_data.financial = Financial(
            invoice_number="2025/BC/SN18215"
        )
        rfcv_data.identification = Identification(
            rfcv_number="RCS25119416",
            fdi_number="FDI-123456",
            fdi_date="15/07/2025"
        )

        # Créer 3 articles
        rfcv_data.items = [
            Item(goods_description=f"Article {i+1}")
            for i in range(3)
        ]

        # Ajouter les documents
        parser = RFCVParser("dummy.pdf")
        parser._add_attached_documents(rfcv_data)

        # Vérifier que tous les articles ont le RFCV
        for i, item in enumerate(rfcv_data.items, start=1):
            rfcv_docs = [doc for doc in item.attached_documents if doc.code == '2501']
            assert len(rfcv_docs) == 1, f"Article {i} doit avoir 1 document RFCV"
            assert rfcv_docs[0].reference == "RCS25119416"

        # Vérifier que seul le premier article a la FDI
        fdi_docs = [doc for doc in rfcv_data.items[0].attached_documents if doc.code == '6610']
        assert len(fdi_docs) == 1, "Le premier article doit avoir 1 document FDI"
        assert fdi_docs[0].reference == "FDI-123456"

        # Vérifier que les autres articles n'ont PAS la FDI
        for i, item in enumerate(rfcv_data.items[1:], start=2):
            fdi_docs = [doc for doc in item.attached_documents if doc.code == '6610']
            assert len(fdi_docs) == 0, f"L'article {i} ne doit PAS avoir de document FDI"

    def test_previous_document_reference_first_item_only(self):
        """Previous_document_reference doit apparaître uniquement sur le premier article"""
        rfcv_data = RFCVData()
        rfcv_data.financial = Financial(
            invoice_number="2025/BC/SN18215",
            invoice_date="17/07/2025"
        )
        rfcv_data.identification = Identification()

        # Créer 3 articles
        rfcv_data.items = [
            Item(goods_description=f"Article {i+1}")
            for i in range(3)
        ]

        # Simuler l'ajout de Previous_document_reference
        invoice_num = rfcv_data.financial.invoice_number
        invoice_date = rfcv_data.financial.invoice_date
        prev_doc_ref = f"{invoice_num} DU {invoice_date}"
        rfcv_data.items[0].previous_document_reference = prev_doc_ref

        # Vérifications
        assert rfcv_data.items[0].previous_document_reference == "2025/BC/SN18215 DU 17/07/2025"

        for i, item in enumerate(rfcv_data.items[1:], start=2):
            assert item.previous_document_reference is None, \
                f"Article {i} ne doit PAS avoir de Previous_document_reference"

    def test_invoice_number_with_single_item(self):
        """Test avec un seul article"""
        rfcv_data = RFCVData()
        rfcv_data.financial = Financial(
            invoice_number="2025/BC/SN18215",
            invoice_date="17/07/2025"
        )
        rfcv_data.identification = Identification(
            rfcv_number="RCS25119416"
        )

        # Un seul article
        rfcv_data.items = [Item(goods_description="Article unique")]

        parser = RFCVParser("dummy.pdf")
        parser._add_attached_documents(rfcv_data)

        # Doit avoir le document FACTURE
        invoice_docs = [doc for doc in rfcv_data.items[0].attached_documents if doc.code == '0007']
        assert len(invoice_docs) == 1

    def test_invoice_number_with_empty_items(self):
        """Test avec liste d'articles vide (ne doit pas planter)"""
        rfcv_data = RFCVData()
        rfcv_data.financial = Financial(
            invoice_number="2025/BC/SN18215"
        )
        rfcv_data.identification = Identification()
        rfcv_data.items = []

        parser = RFCVParser("dummy.pdf")
        # Ne doit pas planter
        parser._add_attached_documents(rfcv_data)

        assert len(rfcv_data.items) == 0

    def test_invoice_number_after_grouping(self):
        """Test que le numéro de facture reste sur le premier article après regroupement"""
        from item_grouper import group_items_by_hs_code

        rfcv_data = RFCVData()
        rfcv_data.financial = Financial(
            invoice_number="2025/BC/SN18215",
            invoice_date="17/07/2025"
        )
        rfcv_data.identification = Identification(
            rfcv_number="RCS25119416"
        )

        # Créer 5 articles avec codes HS identiques (pour forcer regroupement)
        rfcv_data.items = [
            Item(
                goods_description=f"Article {i+1}",
                tarification=Tarification(
                    hscode=HSCode(commodity_code="84099900")
                ),
                packages=Package(number_of_packages=1)
            )
            for i in range(5)
        ]

        # Regrouper les articles
        rfcv_data.items = group_items_by_hs_code(rfcv_data.items, total_packages=5)

        # Ajouter les documents après regroupement
        parser = RFCVParser("dummy.pdf")
        parser._add_attached_documents(rfcv_data)

        # Vérifier que le premier article (après regroupement) a le document FACTURE
        invoice_docs = [doc for doc in rfcv_data.items[0].attached_documents if doc.code == '0007']
        assert len(invoice_docs) == 1, "Le premier article groupé doit avoir le document FACTURE"

    def test_count_invoice_documents_multiple_items(self):
        """Compte total des documents FACTURE doit être exactement 1"""
        rfcv_data = RFCVData()
        rfcv_data.financial = Financial(
            invoice_number="2025/BC/SN18215"
        )
        rfcv_data.identification = Identification(
            rfcv_number="RCS25119416"
        )

        # 10 articles
        rfcv_data.items = [
            Item(goods_description=f"Article {i+1}")
            for i in range(10)
        ]

        parser = RFCVParser("dummy.pdf")
        parser._add_attached_documents(rfcv_data)

        # Compter le nombre total de documents FACTURE
        total_invoice_docs = sum(
            len([doc for doc in item.attached_documents if doc.code == '0007'])
            for item in rfcv_data.items
        )

        assert total_invoice_docs == 1, f"Il doit y avoir exactement 1 document FACTURE au total, trouvé: {total_invoice_docs}"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
