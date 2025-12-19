# agents/simple_text_parser.py
import re

def quick_parse_invoice_text(text: str) -> dict:
    text = text or ""
    out = {
        "vendor": "",
        "invoice_no": "",
        "invoice_date": "",
        "payment_terms": "",
        "tax_amount": 0.0,
        "total_price": 0.0,
        "items": []
    }
    # vendor
    m = re.search(r"Vendor Name[:\s]*([A-Za-z0-9 &.,\-]+)", text)
    if m:
        out["vendor"] = m.group(1).strip()
    m = re.search(r"Invoice Number[:\s]*([A-Za-z0-9_\-]+)", text)
    if m:
        out["invoice_no"] = m.group(1).strip()
    m = re.search(r"Date[:\s]*([0-9]{1,2}[-/][A-Za-z0-9]{3,}[-/][0-9]{4}|[0-9]{2}-[A-Za-z]{3}-[0-9]{4})", text)
    if m:
        out["invoice_date"] = m.group(1).strip()
    m = re.search(r"Total Amount[:\s]*INR\s*([0-9.,]+)", text)
    if not m:
        m = re.search(r"Total Amount[:\s]*([0-9.,]+)", text)
    if m:
        out["total_price"] = float(m.group(1).replace(",", ""))
    m = re.search(r"Tax.*?[:\s]*INR\s*([0-9.,]+)", text)
    if m:
        out["tax_amount"] = float(m.group(1).replace(",", ""))
    # quick items: lines with pattern name qty unit price total
    lines = text.splitlines()
    for line in lines:
        parts = line.strip().split()
        # heuristic: lines with at least 4 tokens and contain a numeric price
        if len(parts) >= 4 and re.search(r"\d+\.\d{1,2}", line):
            # attempt last 3 tokens as qty unit price total
            try:
                total = float(parts[-1].replace(",", ""))
                price = float(parts[-2].replace(",", ""))
                qty = float(parts[-3])
                name = " ".join(parts[:-3])
                out["items"].append({
                    "material_name": name.strip(),
                    "quantity": qty,
                    "unit": "",
                    "unit_price": price,
                    "line_total": total
                })
            except Exception:
                continue
    return out
