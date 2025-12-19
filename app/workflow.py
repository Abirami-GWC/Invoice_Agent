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

def node_analyze(state: InvoiceState) -> InvoiceState:
    new_state = dict(state)
    invoice = new_state.get("parsed_invoice") or {}

    current_date = get_current_date()
    historical_df = load_historical_dataset()

    # -------------------------------------------------
    # 1️⃣ Analyzer LLM — FULL reasoning authority
    # -------------------------------------------------
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

    # 🔑 CRITICAL: Inject analyzer output into invoice
    invoice["analyzed_detailed"] = analyzer_payload
    new_state["analyzed_detailed"] = analyzer_payload

    # -------------------------------------------------
    # 2️⃣ Summary LLM — reporting only
    # -------------------------------------------------
    summary_result = llm_prepare_anomaly_output(
        parsed=invoice,                 # contains analyzed_detailed
        historical_df=historical_df,
        current_date=current_date,
    )

    summary_payload = (
        summary_result.model_dump()
        if hasattr(summary_result, "model_dump")
        else dict(summary_result)
    )

    new_state["analyzed_summary"] = summary_payload
    new_state["invoice_summary"] = summary_payload.get("anomaly_one_line")

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
    finance_email_address = new_state.get("finance_email")

    # -----------------------------
    # Save dataset rows
    # -----------------------------
    for item in detailed.get("invoice", {}).get("items", []):
        append_to_csv({
            "thread_id": new_state.get("thread_id"),
            "Invoice_No": detailed["invoice"].get("invoice_no"),
            "Vendor_Name": detailed["invoice"].get("vendor"),
            "Date": detailed["invoice"].get("invoice_date"),
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
            "manager_comment": decision.get("comment"),
        })

    # -----------------------------
    # FINANCE EMAIL (ALWAYS)
    # -----------------------------
    if finance_email_address and summary.get("email_body_finance"):
        send_to_finance(
            summary=summary,
            detailed_invoice=detailed.get("invoice", {}),
            finance_email=finance_email_address
        )

    # -----------------------------
    # VENDOR EMAIL (ONLY IF REJECTED)
    # -----------------------------
    if not approve and summary.get("email_body_vendor"):
        send_to_vendor(
            parsed_invoice=detailed.get("invoice", {}),
            vendor_email=summary.get("email_subject_vendor")
        )

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
