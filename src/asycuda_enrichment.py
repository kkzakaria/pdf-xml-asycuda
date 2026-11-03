"""
Champs calculés attendus par ASYCUDA, appliqués après la répartition proportionnelle.

Règles relevées sur les XML de production (28923, 28928) et l'export ASYCUDA réel 28926 :

Par article (montants nationaux arrondis à l'unité) :
  - Item_Invoice national       = round(FOB article × taux)
  - item_external_freight nat.  = round(fret article (devise) × taux)
  - Total_cost_itm              = fret + assurance
  - Total_CIF_itm               = FOB + fret + assurance
  - Statistical_value           = Total_CIF_itm
  - Value_item                  = « fret+0+assurance+0-0 », milliers séparés par « , »
                                  (ex. 83,012+0+491+0-0)
  - Number_of_packages          = total colis réparti à parts égales sur les articles avec
                                  châssis, le reste aux premiers articles (423 / 35 -> 3×13 + 32×12)

Global :
  - Total_cost = Value_details  = Σ (fret + assurance)
  - Total_CIF                   = Σ CIF articles
  - Gs_external_freight nat.    = round(fret total × taux)
"""

from models import RFCVData


def to_asycuda_date(value: str | None) -> str | None:
    """'27/07/2026' -> '7/27/26' (format des dates de documents joints dans ASYCUDA)."""
    if not value:
        return value
    parts = value.strip().split("/")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        return value
    day, month, year = (int(p) for p in parts)
    return f"{month}/{day}/{year % 100:02d}"


def format_value_item(freight: int, insurance: int) -> str:
    """Case 44 « Éléments de valeur » : fret + fret interne + assurance + autres - déductions."""
    return f"{freight:,}+0+{insurance:,}+0-0"


def distribute_evenly(total: int, count: int) -> list:
    """Répartition à parts égales, le reste aux premiers éléments."""
    base, rest = divmod(total, count)
    return [base + 1 if i < rest else base for i in range(count)]


def enrich_for_asycuda(rfcv_data: RFCVData) -> RFCVData:
    items = rfcv_data.items
    if not items:
        return rfcv_data

    fin = rfcv_data.financial
    rate = fin.exchange_rate if fin and fin.exchange_rate else None
    total_cost = 0
    total_cif = 0

    for item in items:
        vi = item.valuation_item
        tarif = item.tarification
        if vi is None or tarif is None or tarif.item_price is None or rate is None:
            continue

        inv_nat = round(tarif.item_price * rate)
        if vi.invoice:
            vi.invoice.amount_national = float(inv_nat)

        efr_nat = 0
        if vi.external_freight and vi.external_freight.amount_foreign is not None:
            efr_nat = round(vi.external_freight.amount_foreign * rate)
            vi.external_freight.amount_national = float(efr_nat)

        ins_nat = 0
        if vi.insurance and vi.insurance.amount_national is not None:
            ins_nat = round(vi.insurance.amount_national)

        vi.total_cost = float(efr_nat + ins_nat)
        vi.total_cif = float(inv_nat + efr_nat + ins_nat)
        vi.statistical_value = vi.total_cif
        tarif.value_item = format_value_item(efr_nat, ins_nat)
        total_cost += efr_nat + ins_nat
        total_cif += inv_nat + efr_nat + ins_nat

    # Colis : uniquement quand tous les articles portent un châssis (sinon le regroupement
    # par code SH a déjà placé le total sur le premier article)
    total_packages = rfcv_data.property.total_packages if rfcv_data.property else None
    if total_packages and all(i.packages and i.packages.chassis_number for i in items):
        for item, n in zip(items, distribute_evenly(int(total_packages), len(items))):
            item.packages.number_of_packages = float(n)

    val = rfcv_data.valuation
    if val is not None and rate is not None:
        val.total_cost = float(total_cost)
        val.total_cif = float(total_cif)
        rfcv_data.value_details = float(total_cost)
        if val.external_freight and val.external_freight.amount_foreign is not None:
            val.external_freight.amount_national = float(round(val.external_freight.amount_foreign * rate))
        if val.invoice and val.invoice.amount_foreign is not None:
            val.invoice.amount_national = float(round(val.invoice.amount_foreign * rate))
    return rfcv_data
