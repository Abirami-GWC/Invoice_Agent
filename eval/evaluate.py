"""
Accuracy evaluation for the Invoice Validation & Approval Agent.

  python eval/evaluate.py          -> Stage A (OCR) + Stage B (Python validation layer)
  python eval/evaluate.py --llm    -> also Stage C: full workflow with Groq (end-to-end)

Run from the project root. Results -> eval/results.json
"""
import sys, os, re, json, io, uuid, contextlib, shutil, copy
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT); sys.path.insert(0, ROOT)
import pytesseract
import services.ocr_extractor as ocr
if not os.path.exists(ocr.pytesseract.pytesseract.tesseract_cmd):
    ocr.pytesseract.pytesseract.tesseract_cmd = shutil.which("tesseract") or "tesseract"
from PIL import Image
import app.workflow as wf

GT = json.load(open("eval/invoices/ground_truth.json"))
CATS = ["clean", "total_mismatch", "line_math_error", "future_date", "unreadable_value", "duplicate_invoice"]
quiet = lambda: contextlib.redirect_stdout(io.StringIO())

def fields(g):
    f = [("invoice_no", g["invoice_no"]), ("vendor", g["vendor"]), ("date", g["invoice_date_printed"]),
         ("payment_terms", g["payment_terms"])]
    for i, it in enumerate(g["items"]):
        f += [(f"item{i}.name", it["material_name"]), (f"item{i}.qty", f'{it["quantity"]} kg'),
              (f"item{i}.unit_price", it["unit_price"] if isinstance(it["unit_price"], str) else f'{it["unit_price"]:.2f}'),
              (f"item{i}.line_total", f'{it["line_total"]:.2f}')]
    f += [("subtotal", f'{g["subtotal"]:.2f}'), ("tax", f'{g["tax_amount"]:.2f}'), ("total", f'{g["total_price"]:.2f}')]
    return f

def found(val, text):
    # collapse whitespace and treat "8kg" == "8 kg"; value must be a whole token
    norm = lambda s: re.sub(r"(\d) ?kg\b", r"\1kg", re.sub(r"\s+", " ", s)).strip()
    return re.search(r"(?<![\w.])" + re.escape(norm(val)) + r"(?![\w])", norm(text)) is not None

# ---------------- Stage A: OCR field accuracy ----------------
def stage_a():
    res = {"pipeline": [0, 0], "raw_tesseract": [0, 0]}; misses = []
    cache_path = "eval/ocr_cache.json"
    cache = json.load(open(cache_path)) if os.path.exists(cache_path) else {}
    for g in GT:
        path = f"eval/invoices/{g['file']}"
        if g["file"] not in cache:
            with quiet(): pipe = ocr.extract_text(open(path, "rb").read(), "image/png")
            raw = pytesseract.image_to_string(Image.open(path))
            cache[g["file"]] = {"pipeline": pipe, "raw": raw}
            json.dump(cache, open(cache_path, "w"))
        pipe, raw = cache[g["file"]]["pipeline"], cache[g["file"]]["raw"]
        for name, val in fields(g):
            for key, txt in [("pipeline", pipe), ("raw_tesseract", raw)]:
                ok = found(val, txt); res[key][0] += ok; res[key][1] += 1
                if key == "pipeline" and not ok: misses.append(f"{g['file']} {name}={val!r}")
    return res, misses

# ---------------- Stage B: Python validation layer (perfect extraction) ----------------
def perfect_extraction(g):
    return {"vendor": g["vendor"], "invoice_no": g["invoice_no"], "invoice_created_date": g["invoice_date_printed"],
            "payment_terms": g["payment_terms"], "tax_amount": g["tax_amount"], "total_price": g["total_price"],
            "items": copy.deepcopy(g["items"])}

def stage_b():
    cap = {}
    wf.llm_analyze_invoice = lambda parsed_invoice, historical_df, current_date: (cap.update(inv=dict(parsed_invoice)) or {})
    wf.llm_prepare_anomaly_output = lambda parsed, historical_df, current_date: {}
    rows = []
    for g in GT:
        with quiet(): wf.node_analyze({"parsed_invoice": perfect_extraction(g)})
        inv = cap["inv"]; pred = set()
        if inv["python_total_mismatch"]: pred.add("TOTAL_MISMATCH")
        if inv["invoice_is_future_date"]: pred.add("FUTURE_DATE")
        rows.append({"file": g["file"], "category": g["category"], "expected": g["expected_anomalies"], "predicted": sorted(pred)})
    return rows

# ---------------- Stage C: full workflow with LLM ----------------
CODE_MAP = [("TOTAL", "TOTAL_MISMATCH"), ("FUTURE", "FUTURE_DATE"), ("DUPLICATE", "DUPLICATE_INVOICE"),
            ("LINE", "LINE_MATH_ERROR"), ("CALC", "LINE_MATH_ERROR"), ("ARITH", "LINE_MATH_ERROR"),
            ("INVALID", "UNREADABLE_VALUE"), ("OCR", "UNREADABLE_VALUE"), ("UNREADABLE", "UNREADABLE_VALUE"),
            ("CORRUPT", "UNREADABLE_VALUE")]

def num(v):
    try: return round(float(str(v).replace(",", "")), 2)
    except: return None

def stage_c():
    rows = []
    for g in GT:
        tid = str(uuid.uuid4()); cfg = {"configurable": {"thread_id": tid}}; st, err = None, None
        try:
            with quiet():
                for ev in wf.workflow.stream({"file_bytes": open(f"eval/invoices/{g['file']}", "rb").read(),
                                              "content_type": "image/png", "thread_id": tid}, config=cfg, stream_mode="values"):
                    st = ev
        except Exception as e: err = repr(e)[:300]
        p = (st or {}).get("parsed_invoice") or {}
        checks = [("invoice_no", p.get("invoice_no") == g["invoice_no"]), ("vendor", p.get("vendor") == g["vendor"]),
                  ("date", p.get("invoice_date") == g["invoice_date_iso"]), ("payment_terms", p.get("payment_terms") == g["payment_terms"]),
                  ("tax", num(p.get("tax_amount")) == g["tax_amount"]), ("total", num(p.get("total_price")) == g["total_price"])]
        pit = p.get("items") or []
        for i, it in enumerate(g["items"]):
            q = pit[i] if i < len(pit) else {}
            checks += [(f"item{i}.name", q.get("material_name") == it["material_name"]),
                       (f"item{i}.qty", num(q.get("quantity")) == it["quantity"]),
                       (f"item{i}.unit_price", (str(q.get("unit_price")).strip() == it["unit_price"]) if isinstance(it["unit_price"], str)
                                               else num(q.get("unit_price")) == it["unit_price"]),
                       (f"item{i}.line_total", num(q.get("line_total")) == it["line_total"])]
        det = (st or {}).get("analyzed_detailed") or {}
        codes = [a.get("code", "") for a in det.get("anomalies", [])] + [f.get("code", "") for f in det.get("field_issues", [])]
        pred = sorted({m for c in codes for k, m in CODE_MAP if k in str(c).upper()})
        rows.append({"file": g["file"], "category": g["category"], "error": err, "field_checks": checks,
                     "expected": g["expected_anomalies"], "predicted": pred, "raw_codes": codes,
                     "severity": ((st or {}).get("analyzed_summary") or {}).get("severity")})
        print(f"  {g['file']} done{' (ERROR)' if err else ''}", file=sys.stderr)
    return rows

def detection_report(rows, title):
    print(f"\n{title}")
    print(f"  {'category':18s} {'n':>3s}  correct verdict")
    tot_ok = 0
    for c in CATS:
        rs = [r for r in rows if r["category"] == c]
        ok = sum(1 for r in rs if (set(r["expected"]) <= set(r["predicted"])) and (r["expected"] or not r["predicted"]))
        tot_ok += ok; print(f"  {c:18s} {len(rs):3d}  {ok}/{len(rs)}")
    anom = [r for r in rows if r["expected"]]; clean = [r for r in rows if not r["expected"]]
    tp = sum(1 for r in anom if set(r["expected"]) & set(r["predicted"])); fp = sum(1 for r in clean if r["predicted"])
    print(f"  overall correct verdict: {tot_ok}/{len(rows)} = {tot_ok/len(rows):.1%}")
    print(f"  anomaly recall (flagged anomalous invoices): {tp}/{len(anom)} = {tp/len(anom):.1%}")
    print(f"  false positives on clean invoices: {fp}/{len(clean)}")
    return {"correct": tot_ok, "n": len(rows), "recall": tp / len(anom), "fp": fp, "n_clean": len(clean)}

if __name__ == "__main__":
    out = {}
    a, misses = stage_a()
    print(f"STAGE A - OCR field accuracy ({len(GT)} invoices, {a['pipeline'][1]} fields)")
    for k, (ok, n) in a.items(): print(f"  {k:14s} {ok}/{n} = {ok/n:.1%}")
    print("  pipeline OCR misses (first 15):"); [print("   ", m) for m in misses[:15]]
    out["stage_a"] = {"scores": a, "misses": misses}
    rb = stage_b(); out["stage_b"] = {"rows": rb, "summary": detection_report(rb, "STAGE B - Python validation layer, assuming perfect extraction")}
    if "--llm" in sys.argv:
        rc = stage_c(); ok = sum(c[1] for r in rc for c in r["field_checks"]); n = sum(len(r["field_checks"]) for r in rc)
        print(f"\nSTAGE C - End-to-end (OCR + Groq LLM)\n  extraction field accuracy: {ok}/{n} = {ok/n:.1%}")
        print(f"  invoices fully extracted correctly: {sum(all(c[1] for c in r['field_checks']) for r in rc)}/{len(rc)}")
        print(f"  runs with errors: {sum(1 for r in rc if r['error'])}/{len(rc)}")
        out["stage_c"] = {"rows": rc, "field_accuracy": ok / n, "summary": detection_report(rc, "  anomaly detection (LLM)")}
    json.dump(out, open("eval/results.json", "w"), indent=1, default=str)
