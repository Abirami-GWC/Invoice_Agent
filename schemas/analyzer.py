## File: `schemas/analyzer.py`
from pydantic import BaseModel
from typing import List, Optional, Dict, Any


class Evidence(BaseModel):
    attempts: Optional[str] = None
    parsed_value: float | str | None = None
    historical_avg: Optional[float] = None
    deviation_pct: Optional[float] = None

    
class FieldIssue(BaseModel):
    field: str
    code: str
    value: Any
    evidence: Evidence
    severity: str
    confidence: float
    recommended_action: str


class AnomalyEvidence(BaseModel):
    computed_subtotal: Optional[float] = None
    provided_total: Optional[float] = None
    expected_total: Optional[float] = None
    difference: Optional[float] = None


class Anomaly(BaseModel):
    code: str
    description: str
    severity: str
    confidence: float
    evidence: AnomalyEvidence


class Computed(BaseModel):
    computed_subtotal: Optional[float] = None
    computed_expected_total: Optional[float] = None
    notes: Optional[str] = None


class EmailFinance(BaseModel):
    subject: str
    body: str


class EmailVendor(BaseModel):
    subject: Optional[str] = None
    body: Optional[str] = None


class AnalyzerResult(BaseModel):
    invoice: Dict[str, Any]
    computed: Computed
    field_issues: List[FieldIssue]
    anomalies: List[Anomaly]
    email_body_finance: EmailFinance
    email_body_vendor: EmailVendor
    summary: str
