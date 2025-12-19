from pydantic import BaseModel
from typing import Optional, Dict, Any, List


class AnomalyResult(BaseModel):
    anomaly_one_line: str
    reason: str
    recommendation: str
    severity: str               # "Low" | "Medium" | "High"
    confidence: int             # 0–100

    email_subject_finance: str
    email_body_finance: str

    email_subject_vendor: Optional[str] = None
    email_body_vendor: Optional[str] = None

    # Add these for frontend rendering
    vendor_name: Optional[str] = None
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    tax_amount: Optional[float] = None
    total_price: Optional[float] = None
    items: Optional[List[Dict[str, Any]]] = None
