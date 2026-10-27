"""Generate a labelled synthetic invoice test set (images + ground truth JSON)."""
import json, random, os, sys
from datetime import date, timedelta
from PIL import Image, ImageDraw, ImageFont, ImageFilter

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "invoices")
os.makedirs(OUT, exist_ok=True)
rng = random.Random(42)
TODAY = date(2026, 10, 26)

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/crosextra/Carlito-Regular.ttf",
    "/usr/share/fonts/truetype/lato/Lato-Regular.ttf",
    "C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/calibri.ttf",
]
FONTS = [f for f in FONT_CANDIDATES if os.path.exists(f)]

VENDORS = ["FreshHarvest Ltd", "GrainMill Co", "Dairy Delights", "Golden Grains", "FreshFarm Produce",
           "Spice Route Traders", "Green Valley Foods", "Sunrise Wholesale"]
ITEMS = {"Turmeric": 50, "Butter": 60, "Milk": 54, "Wheat Flour": 50, "Rice": 45, "Sugar": 42,
         "Salt": 20, "Paneer": 320, "Banana": 40, "Coriander": 90, "Ghee": 550, "Oats": 120}
TERMS = ["Net 15 Days", "Net 30 Days", "Net 45 Days", "Net 60 Days"]
DATE_FMTS = ["%d-%b-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d %b %Y", "%b %d, %Y"]

# category -> count
PLAN = [("clean", 20), ("total_mismatch", 6), ("line_math_error", 6),
        ("future_date", 6), ("unreadable_value", 6), ("duplicate_invoice", 2)]

def money(x): return f"{x:.2f}"

def build(idx, cat, used_numbers):
    vendor = rng.choice(VENDORS)
    if cat == "duplicate_invoice" and used_numbers:
        inv_no, vendor = rng.choice(used_numbers)
    else:
        inv_no = f"INV-{2026}{idx:04d}"
    used_numbers.append((inv_no, vendor))
    if cat == "future_date":
        d = TODAY + timedelta(days=rng.randint(5, 200))
    else:
        d = TODAY - timedelta(days=rng.randint(5, 400))
    fmt = DATE_FMTS[idx % len(DATE_FMTS)]
    names = rng.sample(list(ITEMS), rng.randint(3, 5))
    items = []
    for n in names:
        q = rng.randint(5, 60)
        p = round(ITEMS[n] * rng.uniform(0.9, 1.1), 2)
        items.append({"material_name": n, "quantity": q, "unit": "kg", "unit_price": p,
                      "line_total": round(q * p, 2)})
    labels = []
    if cat == "line_math_error":
        it = rng.choice(items); it["line_total"] = round(it["line_total"] + rng.choice([100, 250, 500, 1000]), 2)
        labels.append("LINE_MATH_ERROR")
    sub = round(sum(i["line_total"] for i in items), 2)
    tax = round(sub * 0.05, 2)
    total = round(sub + tax, 2)
    if cat == "total_mismatch":
        total = round(total + rng.choice([-300, -120.5, 75, 200, 999]), 2); labels.append("TOTAL_MISMATCH")
    if cat == "future_date": labels.append("FUTURE_DATE")
    unreadable = None
    if cat == "unreadable_value":
        it = rng.choice(items); unreadable = it["material_name"]
        it["unit_price"] = rng.choice(["INVALID", "N/A", "##.##"]); labels.append("UNREADABLE_VALUE")
    if cat == "duplicate_invoice": labels.append("DUPLICATE_INVOICE")
    return {"file": f"inv_{idx:03d}.png", "category": cat, "expected_anomalies": labels,
            "invoice_no": inv_no, "vendor": vendor, "invoice_date_iso": d.isoformat(),
            "invoice_date_printed": d.strftime(fmt), "payment_terms": rng.choice(TERMS),
            "items": items, "subtotal": sub, "tax_amount": tax, "total_price": total}

def render(gt, path, idx):
    font_path = FONTS[idx % len(FONTS)]
    W, H = 1240, 1500
    img = Image.new("RGB", (W, H), "white"); d = ImageDraw.Draw(img)
    f = ImageFont.truetype(font_path, 30); fb = ImageFont.truetype(font_path, 40)
    d.text((W // 2 - 160, 80), "Purchase Invoice", font=fb, fill="black")
    y = 190
    for k, v in [("Invoice Number", gt["invoice_no"]), ("Vendor Name", gt["vendor"]),
                 ("Date", gt["invoice_date_printed"]), ("Payment Terms", gt["payment_terms"])]:
        d.text((80, y), f"{k}: {v}", font=f, fill="black"); y += 60
    y += 30; cols = [80, 420, 620, 880, 1160]
    rows = [["Item", "Quantity", "Unit Price (INR)", "Total (INR)"]] + [
        [i["material_name"], f'{i["quantity"]} {i["unit"]}',
         i["unit_price"] if isinstance(i["unit_price"], str) else money(i["unit_price"]), money(i["line_total"])]
        for i in gt["items"]]
    for r in rows:
        d.rectangle([cols[0], y, cols[-1], y + 70], outline="black", width=2)
        for c in range(4):
            d.line([cols[c], y, cols[c], y + 70], fill="black", width=2)
            d.text((cols[c] + 15, y + 18), str(r[c]), font=f, fill="black")
        y += 70
    y += 40
    for k, v in [("Subtotal", gt["subtotal"]), ("Tax (5%)", gt["tax_amount"]), ("Total Amount", gt["total_price"])]:
        d.text((80, y), f"{k}: INR {money(v)}", font=f, fill="black"); y += 60
    # every 3rd invoice: simulate a scan (slight rotation + blur + downscale)
    if idx % 3 == 0:
        img = img.rotate(rng.uniform(-1.2, 1.2), expand=False, fillcolor="white")
        img = img.filter(ImageFilter.GaussianBlur(0.8)).resize((W * 3 // 4, H * 3 // 4))
    img.save(path)

if __name__ == "__main__":
    gts, used, idx = [], [], 1
    order = [c for c, n in PLAN for _ in range(n)]
    for cat in order:
        gt = build(idx, cat, used); render(gt, os.path.join(OUT, gt["file"]), idx); gts.append(gt); idx += 1
    json.dump(gts, open(os.path.join(OUT, "ground_truth.json"), "w"), indent=1)
    print(f"generated {len(gts)} invoices in {OUT}")
