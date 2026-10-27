from agents.invoice_anomaly_agent import analyze_and_prepare
import pandas as pd

# Mock a small historical dataset for testing
data = [
    {"Vendor_Name": "FreshHarvest Ltd", "Item": "Turmeric", "Unit_Price": 48},
    {"Vendor_Name": "FreshHarvest Ltd", "Item": "Butter", "Unit_Price": 60},
    {"Vendor_Name": "FreshHarvest Ltd", "Item": "Wheat Flour", "Unit_Price": 50},
]
historical_df = pd.DataFrame(data)

# paste the parsed JSON you got
parsed_invoice = {
    "vendor": "FreshHarvest Ltd",
    "invoice_no": "MULTL_INVX101",
    "invoice_created_date": "06-Jul-2026",
    "payment_terms": "Net 30 Days",
    "tax_amount": 311.97,
    "total_price": 6551.29,
    "items": [
        {"material_name": "Turmeric", "quantity": 45, "unit": "kg", "unit_price": 50.32, "line_total": 2264.4},
        {"material_name": "Butter", "quantity": 16, "unit": "kg", "unit_price": 59.26, "line_total": 948.16},
        {"material_name": "Milk", "quantity": 12, "unit": "kg", "unit_price": None, "line_total": 647.4},
        {"material_name": "Wheat Flour", "quantity": 48, "unit": "kg", "unit_price": 49.57, "line_total": 2379.36},
    ]
}

plain_text, enriched = analyze_and_prepare(parsed_invoice, historical_df)

print("\n=== SUMMARY TEXT ===")
print(plain_text)

print("\n=== ANOMALY OUTPUT ===")
import json
print(json.dumps(enriched, indent=2))
