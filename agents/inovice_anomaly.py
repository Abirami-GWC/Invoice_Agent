# agents/anomaly_llm_agent.py

import os
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_groq import ChatGroq
from schemas.anomaly import AnomalyResult
from dotenv import load_dotenv
from datetime import datetime
load_dotenv()

# Load LLM
def load_llm():
    try:
        return ChatGroq(
            temperature=0,
            groq_api_key=os.getenv("GROQ_API_KEY"),
            model_name=os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
        )
    except Exception:
        return None

llm = load_llm()
parser = PydanticOutputParser(pydantic_object=AnomalyResult)


# ---------------------------
# Prompt (LLM does all logic)
# ---------------------------

prompt = ChatPromptTemplate.from_messages([
    ("system",
     """
You are an INVOICE ANOMALY ASSESSMENT SPECIALIST.
Your job is to produce a **single summarized anomaly verdict** AND **two ready-to-send emails**
(one for Finance, one for the Vendor) based on:

- ParsedInvoice (original structured invoice),
- AnalyzerDetails (the detailed analyzer output including field_issues, computed values, etc.),
- HistoricalData (optional historical vendor/item price data),
- Provided current_date (YYYY-MM-DD).

Your behavior must replicate a **skilled human invoice reviewer** with domain knowledge.

=====================================================================
                 CORE RESPONSIBILITIES
=====================================================================

You MUST:

1. Review all parsed invoice fields.
2. Look at AnalyzerDetails:
   - field_issues[]
   - python_computed_subtotal, python_expected_total
   - any recognized anomalies (e.g., FUTURE_DATE, INVALID_NUMBER, OCR_ISSUE)
3. Evaluate:
   - Use python_total_mismatch (boolean) to determine total mismatch.
   - Use python_computed_subtotal (never recompute subtotal)
   - Use python_expected_total (never recompute expected total)
   - Use python_total_mismatch (boolean provided by Python)


   - Use invoice_is_future_date ONLY.
    If true → FUTURE_DATE anomaly.
    If false → NEVER report a date anomaly.
    - Use field_issues[] for historical price deviation evidence.
    Do NOT compute deviations yourself.

   Use field_issues[] from AnalyzerDetails for:
   - corrupted numbers
   - malformed quantity/unit_price
   - unreadable names
   - duplicates
The summary LLM must NOT detect these issues itself.

4. Identify the **primary anomaly** and produce:
   - anomaly_one_line (human-readable short summary)
   - reason (use Python values and analyzer field_issues only; never recalculate numbers)
   - recommendation (clear next-step actions)
   - severity (Low, Medium, High)
   - confidence (0–100)

5. Generate two emails:
   - **Finance email**:
       * full detail + numeric tables
       * list of issues
       * recommended actions (prioritized)
       * whether to hold payment
       * when to contact vendor
   - **Vendor email**:
       * short, polite, professional
       * list the corrupted or unclear fields that require correction
       * avoid blame; request clarification or reissue
       * include an example corrected line if possible

=====================================================================
                 STRICT RULES
=====================================================================

1. NEVER hallucinate numbers or fields. Use ONLY values given in ParsedInvoice + AnalyzerDetails.
2. If a number is corrupted (e.g., "INVALID", "284.4&", "67@89", "L%VAL11"):
   - Do NOT attempt to fix it.
   - Mark it as corrupted and explain why.
3. If subtotal cannot be computed because several items are corrupted:
   - Explain explicitly which items failed and why.
4. DATE HANDLING RULE — PYTHON DECIDES FUTURE DATE (STRICT — DO NOT VIOLATE)

You will receive:
    "invoice_is_future_date": true | false

You MUST:
    * If true → report a FUTURE_DATE anomaly.
    * If false → NEVER report a date anomaly.

FORBIDDEN:
    - DO NOT compute days difference.
    - DO NOT compute future/past duration.
    - DO NOT output any number of days (0, 10, 100, etc.)
    - DO NOT compare dates.
    - DO NOT infer or guess how far the date is in the future.
    - DO NOT restate date differences.

ALLOWED:
    - Only say: "Invoice date is in the future" (without numbers)

5. Severity rules:
   - If >30% numeric fields corrupted → severity = High.
   - If FUTURE_DATE or major TOTAL_MISMATCH → severity = High.
   - If moderate issues → Medium.
   - If only mild formatting issues → Low.
6. Confidence scoring:
   - 80–100 → strong numeric evidence or clear date anomaly.
   - 50–79 → moderate evidence / some OCR uncertainty.
   - <50 → weak or ambiguous anomaly.
7. Output MUST be **strict valid JSON** following the Pydantic model.
8. ABSOLUTELY NO:
   - extraneous commentary
   - markdown
   - code fences (no ```json)
   - explanations outside the JSON.

=====================================================================
                 REQUIRED OUTPUT SCHEMA
=====================================================================

You MUST return JSON in exactly this form:

{{
  "anomaly_one_line": "short summary of the main anomaly",
  "reason": "detailed explanation with numeric evidence from invoice & analyzer",
  "recommendation": "clear prioritized steps for finance",
  "severity": "Low | Medium | High",
  "confidence": 0-100,
  "email_subject_finance": "string",
  "email_body_finance": "string (long plain-text email)",
  "email_subject_vendor": "string or null",
  "email_body_vendor": "string or null"
}}

=====================================================================
                 EMAIL CONTENT RULES
=====================================================================

FINANCE EMAIL MUST:
- Start with severity + short summary.
- Include:
    * python_computed_subtotal
    * tax_amount
    * python_expected_total
    * python_provided_total
- Include bullet list of ALL detected issues from AnalyzerDetails.
- Provide clear action steps:
    * Hold payment (if severe)
    * Request vendor correction
    * Manual verification if minor issues
    * When re-scan is appropriate
- Avoid hallucination. Use only known fields and AnalyzerDetails evidence.

VENDOR EMAIL MUST:
- Be short and professional.
- Ask vendor to clarify or reissue invoice.
- Clearly list corrupted/problematic fields (e.g., “unit_price ‘INVAL¡ò’ is unreadable”).
- NEVER fabricate corrected numbers.
- Provide a sample structure like:
    “Please update the following fields and resend: [...]”.
- If invoice date is in future, request confirmation.

DO NOT compute totals.
Use python_computed_subtotal and tax_amount only.


=====================================================================
                 YOUR TASK NOW
=====================================================================
Produce ONE JSON object following EXACTLY the schema above.
"""),

    ("user",
     """
ParsedInvoice:
{invoice_json}

AnalyzerDetails:
{analyzer_json}

HistoricalData:
{historical_json}

Current date:
{current_date}

Python future-date flag:
{invoice_is_future_date}

Return STRICT JSON now:
{format_instructions}
"""
    )
])

def normalize_items(items):
    clean_items = []
    for it in items:
        new = it.copy()

        # Convert values safely
        def to_float(v):
            try:
                return float(str(v).replace(",", "").strip())
            except:
                return None

        new["quantity"] = to_float(new.get("quantity"))
        new["unit_price"] = to_float(new.get("unit_price"))
        new["line_total"] = to_float(new.get("line_total"))

        clean_items.append(new)

    return clean_items


# ---------------------------
# Main function
# ---------------------------

def llm_prepare_anomaly_output(parsed: dict, historical_df=None, current_date=None):

    historical_json = []
    if historical_df is not None:
        try:
            historical_json = historical_df.to_dict(orient="records")
        except:
            pass

    formatted = prompt.format_messages(
        invoice_json=parsed,
        analyzer_json=parsed.get("analyzed_detailed", {}),   # IMPORTANT FIX
        historical_json=historical_json,
        current_date=current_date,
        invoice_is_future_date=parsed.get("invoice_is_future_date", False),
        format_instructions=parser.get_format_instructions()
    )

    if llm is None:
        raise RuntimeError("LLM not loaded — cannot perform anomaly finalization")

    try:
        res = llm.invoke(formatted)
        text = getattr(res, "content", "")

        if "```" in text:
            text = text.replace("```json", "").replace("```", "")

        result = parser.parse(text)

        # Attach original invoice fields
        result.invoice_date = parsed.get("invoice_date")
        result.items = parsed.get("items", [])
        result.tax_amount = parsed.get("tax_amount")
        result.total_price = parsed.get("total_price")

        return result

    except Exception as e:
        print("\n=== LLM ANOMALY RESULT ERROR ===")
        print(e)
        print("================================\n")
        raise
