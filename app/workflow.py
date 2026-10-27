# app/workflow.py

from langgraph.graph import START, StateGraph, END
from langgraph.types import interrupt
from langgraph.checkpoint.memory import MemorySaver

from agents.invoice_extractor_agent import llm_parse_text_to_invoice

# LLM anomaly agents
from agents.invoice_analyzer import llm_analyze_invoice
from agents.inovice_anomaly import llm_prepare_anomaly_output

from agents.invoice_email_agent import send_to_finance, send_to_vendor
from services.dataset_append import load_historical_dataset, append_to_csv
from services.ocr_extractor import extract_text

from datetime import datetime


# -------------------------------------------------------
# SYSTEM DATE
# -------------------------------------------------------
def get_current_date():
    """Always return system date in YYYY-MM-DD."""
    return datetime.today().strftime("%Y-%m-%d")


# -------------------------------------------------------
# STRICT PYTHON-BASED FUTURE DATE CHECK
# -------------------------------------------------------
def is_future_date(invoice_date_str: str, current_date_str: str) -> bool:
    """
    Python decides future date instead of LLM.
    Eliminates string-comparison mistakes by LLM.
    """
    try:
        d1 = datetime.strptime(invoice_date_str, "%Y-%m-%d")
        d2 = datetime.strptime(current_date_str, "%Y-%m-%d")
        return d1 > d2
    except:
        return False


# -------------------------------------------------------
# DATE NORMALIZATION UTILITY
# -------------------------------------------------------
def normalize_date(date_str: str) -> str:
    """Convert many date formats into YYYY-MM-DD."""
    if not date_str:
        return ""

    patterns = [
        "%d-%b-%Y", "%d-%B-%Y",
        "%d/%b/%Y", "%d/%B/%Y",
        "%d-%m-%Y", "%d/%m/%Y",
        "%Y-%m-%d",
    ]

    for fmt in patterns:
        try:
            d = datetime.strptime(date_str.strip(), fmt)
            return d.strftime("%Y-%m-%d")
        except:
            continue

    return date_str


# -------------------------------------------------------
# STATE STRUCTURE
# -------------------------------------------------------
class InvoiceState(dict):
    file_bytes: bytes
    content_type: str
    raw_text: str
    parsed_invoice: dict
    analyzed_detailed: dict
    analyzed_summary: dict
    manager_decision: dict
    finance_email: str


graph = StateGraph(InvoiceState)


# -------------------------------------------------------
# NODE 1 — OCR
# -------------------------------------------------------
def node_ocr(state: InvoiceState) -> InvoiceState:
    new_state = dict(state)

    file_bytes = new_state.get("file_bytes", b"")
    content_type = new_state.get("content_type", "")

    raw_text = extract_text(file_bytes, content_type)

    print("\n===== DEBUG OCR OUTPUT =====")
    print(raw_text)
    print("=============================\n")

    new_state["raw_text"] = raw_text
    return new_state


# -------------------------------------------------------
# NODE 2 — Extraction
# -------------------------------------------------------
def node_extract(state: InvoiceState) -> InvoiceState:
    new_state = dict(state)
    raw_text = new_state.get("raw_text", "")

    parsed = llm_parse_text_to_invoice(raw_text)

    # Convert to dict
    if hasattr(parsed, "model_dump"):
        parsed_dict = parsed.model_dump()
    elif hasattr(parsed, "dict"):
        parsed_dict = parsed.dict()
    else:
        parsed_dict = dict(parsed or {})

    # Normalize all possible date fields
    date_fields = [
        "invoice_date",
        "invoice_created_date",
        "date",
        "invoice_dt",
        "bill_date",
        "invoiceDate",
    ]

    normalized_date = None
    for field in date_fields:
        if parsed_dict.get(field):
            normalized_date = normalize_date(parsed_dict[field])
            parsed_dict[field] = normalized_date

    # Always unify into the final required field
    if normalized_date:
        parsed_dict["invoice_date"] = normalized_date

    print("\n🔍 NORMALIZED DATE in node_extract():", normalized_date)

    new_state["parsed_invoice"] = parsed_dict
    return new_state


# -------------------------------------------------------
# NODE 3 — Anomaly Analysis
# -------------------------------------------------------
def node_analyze(state: InvoiceState) -> InvoiceState:
    new_state = dict(state)
    invoice = new_state.get("parsed_invoice") or {}

    # ---------------------------------------------------------
    # 1️⃣ Normalize invoice date ONCE — Python controls the date
    # ---------------------------------------------------------
    date_fields = [
        "invoice_date",
        "invoice_created_date",
        "date",
        "invoice_dt",
        "bill_date",
        "invoiceDate",
    ]

    normalized_date = None
    for field in date_fields:
        if invoice.get(field):
            normalized_date = normalize_date(invoice[field])
            invoice[field] = normalized_date

    if normalized_date:
        invoice["invoice_date"] = normalized_date

    print("\n🔍 FINAL NORMALIZED DATE FOR ANALYSIS:", invoice.get("invoice_date"))

    # ---------------------------------------------------------
    # 2️⃣ PYTHON decides future date (LLM must obey)
    # ---------------------------------------------------------
    current_date = get_current_date()

    invoice_is_future = False
    if invoice.get("invoice_date"):
        invoice_is_future = is_future_date(invoice["invoice_date"], current_date)

    invoice["invoice_is_future_date"] = invoice_is_future
    print("🔍 PYTHON future-date check:", invoice_is_future)

    # ---------------------------------------------------------
    # 3️⃣ PYTHON computes subtotal & expected total (LLM must NOT compute)
    #     RULE: Prefer line_total if available, fallback to qty × unit_price
    # ---------------------------------------------------------
    python_subtotal = 0.0
    items = invoice.get("items", [])

    for it in items:
        # Try line_total first
        line_total_val = None
        try:
            raw_lt = it.get("total") or it.get("line_total")
            if raw_lt not in [None, "", "INVALID"]:
                line_total_val = float(str(raw_lt).replace(",", "").strip())
        except:
            line_total_val = None

        if line_total_val is not None:
            python_subtotal += line_total_val
            continue

        # Fallback: qty * unit_price
        try:
            qty = float(str(it.get("quantity", "0")).replace(",", "").strip())
            price = float(str(it.get("unit_price", "0")).replace(",", "").strip())
            python_subtotal += qty * price
        except:
            continue

    python_subtotal = round(python_subtotal, 2)

    # Tax
    try:
        tax_val = float(str(invoice.get("tax_amount", 0)).replace(",", "").strip())
    except:
        tax_val = 0.0

    python_expected_total = round(python_subtotal + tax_val, 2)

    # Provided total
    try:
        provided_total = float(str(invoice.get("total_price", 0)).replace(",", "").strip())
    except:
        provided_total = None

    python_total_mismatch = (
        provided_total is not None and abs(provided_total - python_expected_total) > 0.01
    )

    # Inject Python calculations into invoice
    invoice["python_computed_subtotal"] = python_subtotal
    invoice["python_expected_total"] = python_expected_total
    invoice["python_provided_total"] = provided_total
    invoice["python_total_mismatch"] = python_total_mismatch

    print("🔢 PYTHON subtotal:", python_subtotal)
    print("🔢 PYTHON expected total:", python_expected_total)
    print("🔢 Provided total:", provided_total)
    print("⚠️ Total mismatch:", python_total_mismatch)

    # Load historical dataset
    historical_df = load_historical_dataset()

    # ---------------------------------------------------------
    # 4️⃣ Detailed anomaly analysis (LLM uses Python values)
    # ---------------------------------------------------------
    analyzer_result = llm_analyze_invoice(
        parsed_invoice=invoice,
        historical_df=historical_df,
        current_date=current_date,
    )

    analyzer_payload = (
        analyzer_result.model_dump()
        if hasattr(analyzer_result, "model_dump")
        else dict(analyzer_result)
    )

    # Store analyzer output so anomaly LLM can use it
    invoice["analyzed_detailed"] = analyzer_payload
    new_state["analyzed_detailed"] = analyzer_payload

    # ---------------------------------------------------------
    # 5️⃣ Final summary anomaly (LLM uses injected Python values)
    # ---------------------------------------------------------
    summary_result = llm_prepare_anomaly_output(
        parsed=invoice,
        historical_df=historical_df,
        current_date=current_date,
    )

    final_summary = (
        summary_result.model_dump()
        if hasattr(summary_result, "model_dump")
        else dict(summary_result)
    )

    new_state["analyzed_summary"] = final_summary
    new_state["invoice_summary"] = final_summary.get("anomaly_one_line")

    return new_state


# -------------------------------------------------------
# NODE 4 — Manager Approval
# -------------------------------------------------------
def node_manager_decision(state: InvoiceState) -> InvoiceState:
    new_state = dict(state)

    payload = {
        "message": "Manager approval required",
        "detailed_anomalies": new_state.get("analyzed_detailed"),
        "summary": new_state.get("analyzed_summary"),
        "invoice_summary": new_state.get("invoice_summary"),
    }

    decision = interrupt(payload)
    new_state["manager_decision"] = decision
    return new_state


# -------------------------------------------------------
# NODE 5 — Route + Save Dataset
# -------------------------------------------------------
def node_route(state: InvoiceState) -> InvoiceState:
    new_state = dict(state)

    summary = new_state.get("analyzed_summary") or {}
    detailed = new_state.get("analyzed_detailed") or {}
    decision = new_state.get("manager_decision") or {}

    approve = decision.get("approve")
    finance_email = new_state.get("finance_email")
    vendor_email = summary.get("vendor_email")

    # Save dataset rows
    for item in detailed.get("invoice", {}).get("items", []):
        append_to_csv({
            "thread_id": new_state.get("thread_id"),
            "Invoice_No": detailed["invoice"].get("invoice_no"),
            "Vendor_Name": detailed["invoice"].get("vendor"),
            "Date": detailed["invoice"].get("invoice_created_date"),
            "Item": item.get("material_name"),
            "Quantity": item.get("quantity"),
            "Unit": item.get("unit"),
            "Unit_Price": item.get("unit_price"),
            "Tax_Amount": detailed["invoice"].get("tax_amount"),
            "Total_Price": detailed["invoice"].get("total_price"),
            "Payment_Terms": detailed["invoice"].get("payment_terms"),
            "Anomaly": summary.get("anomaly_one_line"),
            "Reason": summary.get("reason"),
            "Recommendation": summary.get("recommendation"),
            "Status": "Approved" if approve else "Rejected",
            "Severity": summary.get("severity"),
            "Confidence_Score": summary.get("confidence"),
            "Invoice_Summary": summary.get("anomaly_one_line"),
            "manager_comment": decision.get("comment"),
        })

    # Send email
    if approve and finance_email:
        send_to_finance(summary, finance_email)
    elif not approve and vendor_email:
        send_to_vendor(summary, vendor_email)

    return new_state


def route_after_manager(_state):
    return "route"


# -------------------------------------------------------
# GRAPH SETUP
# -------------------------------------------------------
graph.add_node("ocr", node_ocr)
graph.add_node("extract", node_extract)
graph.add_node("analyze", node_analyze)
graph.add_node("manager_decision", node_manager_decision)
graph.add_node("route", node_route)

graph.add_edge(START, "ocr")
graph.add_edge("ocr", "extract")
graph.add_edge("extract", "analyze")
graph.add_edge("analyze", "manager_decision")

graph.add_conditional_edges("manager_decision", route_after_manager, {"route": "route"})
graph.add_edge("route", END)

memory = MemorySaver()
workflow = graph.compile(checkpointer=memory)
