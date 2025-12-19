import re
from typing import Dict, Any, List


def parse_invoice(text: str) -> Dict[str, Any]:
    data = {}

    # Extract header fields dynamically
    data["invoice_number"] = _find(text, r"Invoice Number[:\s]+(.+)")
    data["vendor_name"] = _find(text, r"Vendor Name[:\s]+(.+)")
    data["invoice_date"] = _find(text, r"Date[:\s]+(.+)")
    data["payment_terms"] = _find(text, r"Payment Terms[:\s]+(.+)")

    # Extract amounts dynamically
    data["subtotal"] = _find_float(text, r"Subtotal[:\s]*INR\s*([0-9.,]+)")
    data["tax_percent"] = _find_float(text, r"Tax\s*\((\d+)%\)")
    data["tax_amount"] = _find_float(text, r"Tax.*INR\s*([0-9.,]+)")
    data["total_amount"] = _find_float(text, r"Total Amount[:\s]*INR\s*([0-9.,]+)")

    # Extract item table automatically
    data["items"] = extract_items(text)

    return data


def extract_items(text: str) -> List[Dict[str, Any]]:
    """
    Dynamically detects table rows assuming format:

    Item | Quantity | Unit Price | Total
    """

    # Find table section between "Item" and "Subtotal"
    table_match = re.search(r"Item(.+?)Subtotal", text, re.S | re.I)
    if not table_match:
        return []

    table_text = table_match.group(1).strip()
    lines = [l.strip() for l in table_text.splitlines() if l.strip()]

    # First line is header row → detect columns dynamically
    header = re.split(r"\s{2,}", lines[0])
    items = []

    for line in lines[1:]:
        cols = re.split(r"\s{2,}", line)
        if len(cols) < len(header):
            continue

        item = {}
        for i, key in enumerate(header):
            normalized = key.lower().replace(" ", "_")
            value = cols[i].strip()

            # Convert numbers
            if re.match(r"^[0-9,.]+$", value.replace("kg", "").strip()):
                try:
                    value = float(value.replace(",", "").replace("kg", "").strip())
                except:
                    pass

            item[normalized] = value

        items.append(item)

    return items


def _find(text: str, pattern: str) -> str:
    m = re.search(pattern, text, re.I)
    return m.group(1).strip() if m else ""


def _find_float(text: str, pattern: str) -> float:
    m = re.search(pattern, text, re.I)
    if not m:
        return 0.0
    return float(m.group(1).replace(",", ""))
