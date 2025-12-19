## File: `agents/pdf_to_json_agent.py`

import json
import textwrap
from models.groq_loader import load_llm

_llm = load_llm()

EXTRACT_PROMPT = textwrap.dedent("""
You are a strict JSON extractor. Given the invoice text below, return ONLY valid JSON (no commentary).
Fields to extract when present:
- VendorName or Vendor
- Invoice_No or InvoiceNo
- Address
- Phone_No
- Mail or Email
- Items (array of objects with keys: material_name, quantity, unit, unit_price, line_total)
- Tax_Amount
- Total_Price
- Payment_Terms
- Invoice_Created_Date
If a field is missing, use null or empty. Items should be an array of objects; if the text doesn't include items, return an empty array.
Invoice text:
{invoice_text}
""")


def _safe_extract_json_from_text(model_text: str):
    if not model_text:
        return {}
    start = model_text.find("{")
    end = model_text.rfind("}")
    if start != -1 and end != -1 and end > start:
        piece = model_text[start:end+1]
        try:
            return json.loads(piece)
        except Exception:
            try:
                return json.loads(piece.replace("'", '"'))
            except Exception:
                pass
    try:
        return json.loads(model_text)
    except Exception:
        return {}


def extract_invoice_json(raw_text: str) -> dict:
    raw_text = "" if raw_text is None else str(raw_text)
    prompt = EXTRACT_PROMPT.format(invoice_text=raw_text[:20000])
    try:
        response = _llm.invoke(prompt)
    except Exception:
        return {}

    content = getattr(response, "content", None) or getattr(response, "text", None) or ""
    parsed = _safe_extract_json_from_text(content)

    items = parsed.get("Items") or parsed.get("items") or []
    if isinstance(items, str):
        try:
            items = json.loads(items)
        except Exception:
            items = []
    parsed["Items"] = items
    return parsed