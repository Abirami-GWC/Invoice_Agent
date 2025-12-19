from pydantic import BaseModel
from typing import List, Optional, Union


# A helper type for corrupted OR numeric OCR fields
NumberOrString = Optional[Union[float, str]]


class InvoiceItem(BaseModel):
    material_name: Optional[str] = None
    quantity: NumberOrString = None      # can be float OR corrupted text string
    unit: Optional[str] = None
    unit_price: NumberOrString = None    # can be float OR corrupted string
    line_total: NumberOrString = None    # can be float OR corrupted string


class InvoiceModel(BaseModel):
    vendor: Optional[str] = None
    invoice_no: Optional[str] = None
    invoice_created_date: Optional[str] = None
    payment_terms: Optional[str] = None

    tax_amount: NumberOrString = None     # numeric or corrupted string
    total_price: NumberOrString = None    # numeric or corrupted string

    items: List[InvoiceItem] = []
