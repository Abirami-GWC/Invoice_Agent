# agents/invoice_analyzer_llm_agent.py

import os
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_groq import ChatGroq
from dotenv import load_dotenv
from schemas.analyzer import AnalyzerResult
from datetime import datetime
current_date = datetime.utcnow().strftime("%Y-%m-%d")

load_dotenv()

# LLM Loader
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
parser = PydanticOutputParser(pydantic_object=AnalyzerResult)


# ---------------------------
# LLM Prompt (Replaces rules)
# ---------------------------

prompt = ChatPromptTemplate.from_messages([
    ("system",
     """
You are an expert INVOICE ANOMALY ANALYZER and HUMAN-LIKE AUDITOR.

Your job is to:
1) Detect ALL anomalies in the invoice.
2) Review every field like a careful human auditor.
3) DO NOT perform your own arithmetic.
   Python already computed accurate numeric values.
   Use ONLY the values:
      python_computed_subtotal
      tax_amount
      total_price

4) Produce NOT ONLY anomalies but also:
     - field-level issues,
     - computed totals,
     - evidence for every anomaly,
     - detailed Finance email (long),
     - short Vendor email (polite).

STRICT RULES (follow all):
1. NEVER hallucinate values. 
2. If a numeric field contains corrupted characters (e.g., "INVALI0", "67@89", "?84.4&"):
      → Treat it as INVALID_NUMBER or OCR_ISSUE.
      → DO NOT fix it. DO NOT guess.
3. DATE HANDLING RULE — PYTHON DECIDES FUTURE DATE (STRICT — DO NOT VIOLATE)

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


4. Show ALL numeric evidence in anomalies, reasoning, and emails.
5. If subtotal cannot be computed, explain why (e.g., “2 of 4 items had invalid totals”).
6. If >30% numeric fields are corrupted → severity HIGH.
7. TOTAL_MISMATCH severity rule:
     - Use ONLY the Python flag "python_total_mismatch".
     - If python_total_mismatch is true → severity = High.
     - If python_total_mismatch is false → do NOT report a total mismatch.
     - Do NOT compute totals, differences, or percentages yourself.

8. If historical_avg exists AND unit_price is numeric:
    compute deviation = (unit_price - historical_avg) / historical_avg * 100
Else:
    skip

9. Output MUST be STRICT JSON. No markdown. No ```json fences.


====================================================================
              WHAT YOU MUST DETECT & COMPUTE
====================================================================

- Expected total mismatch:
    * expected_total = python_expected_total (provided by Python)

====================================================================
              REQUIRED OUTPUT (STRICT JSON)
====================================================================

You MUST RETURN JSON IN EXACTLY THIS FORMAT:

{{
  "invoice": {{ ...original parsed invoice... }},

  "computed": {{
     "computed_subtotal": float or null,
     "computed_expected_total": float or null,
     "notes": "string explaining computations, failures, corrupted rows"
  }},

  "field_issues": [
     {{
       "field": "items[0].unit_price" | "invoice_date" | ...,
       "code": "OCR_ISSUE" | "INVALID_NUMBER" | "MISSING_UNIT" | "FUTURE_DATE" | "TOTAL_MISMATCH" | "PRICE_DEVIATION" | ...,
       "value": "<raw value>",
       "evidence": {{
          "attempts": "float conversion failed: ...",
          "parsed_value": float or null,
          "historical_avg": float or null,
          "deviation_pct": float or null
       }},
       "severity": "Low" | "Medium" | "High",
       "confidence": 0-1,
       "recommended_action": "Rescan/OCR" | "Manual verification" | "Request corrected invoice from vendor" | "Hold payment" | "Accept with approver"
     }}
  ],

  "anomalies": [
     {{
       "code": "FUTURE_DATE" | "TOTAL_MISMATCH" | "INVALID_NUMBER" | "OCR_ISSUE" | "PRICE_DEVIATION" | ...,
       "description": "human-readable explanation with numeric evidence",
       "severity": "Low" | "Medium" | "High",
       "confidence": 0-1,
       "evidence": {{
          "days_future": float or null,
          "computed_subtotal": float or null,
          "provided_total": float or null,
          "expected_total": float or null,
          "difference": float or null
       }}
     }}
  ],

  "email_body_finance": {{
     "subject": "string",
     "body": "long detailed plain-text email with:\\n- anomaly summary\\n- numeric evidence\\n- list of issues\\n- table of computed_subtotal, expected_total, provided_total, tax\\n- prioritized actions"
  }},

  "email_body_vendor": {{
     "subject": "string or null",
     "body": "short polite vendor email asking for corrected invoice or clarification"
  }},

  "summary": "A short overall statement (e.g., '5 anomalies detected; severe numeric corruption')"
}}

====================================================================
              EMAIL RULES
====================================================================

FINANCE EMAIL MUST:
- Begin with severity & anomaly summary.
- Show numeric evidence clearly.
- List ALL issues with short descriptions.
- Include a mini-table:
      computed_subtotal
      provided_subtotal
      tax
      expected_total
      provided_total
- Recommend *specific actions*:
      - HOLD PAYMENT (if severe)
      - Request corrected invoice
      - Manual verification (if minor)
      - OCR rescan (if corrupted)

VENDOR EMAIL MUST:
- Be polite, short, and explain exactly what fields need correction.
- No accusations, no guesses.
- Example: “The following fields could not be read: unit_price ‘INVALI0’, total ‘67@89’.”

====================================================================
                FINAL TASK
====================================================================

Using ParsedInvoice, HistoricalData, and current_date:
→ Analyze EVERYTHING  
→ Produce ALL anomalies  
→ Produce ALL field issues  
→ Produce computed totals  
→ Produce both emails  
→ Return STRICT JSON only  
"""
    ),

    ("user",
     """
ParsedInvoice:
{invoice_json}

HistoricalData:
{historical_json}

Current date:
{current_date}

Python future-date flag:
{invoice_is_future_date}

Return STRICT JSON ONLY:
{format_instructions}
"""
    )
])


# ---------------------------
# Agent Function
# ---------------------------

def llm_analyze_invoice(parsed_invoice: dict, historical_df=None, current_date=current_date):
    """
    LLM-based anomaly analysis. No manual Python calculations.
    """
    historical_json = []
    if historical_df is not None:
        try:
            historical_json = historical_df.to_dict(orient="records")
        except:
            pass

    formatted = prompt.format_messages(
        invoice_json=parsed_invoice,
        # analyzer_json=parsed_invoice.get("analyzed_detailed", {}),
        historical_json=historical_json,
        format_instructions=parser.get_format_instructions(),
        current_date=current_date,
        invoice_is_future_date=parsed_invoice.get("invoice_is_future_date", False)
    )

    if llm is None:
        raise RuntimeError("LLM not loaded — cannot perform invoice anomaly analysis.")

    try:
        res = llm.invoke(formatted)
        text = getattr(res, "content", "")
        if "```" in text:
            text = text.replace("```json", "").replace("```", "")
        return parser.parse(text)
    except Exception as e:
        print("\n=== LLM INVOICE ANALYZER ERROR ===")
        print(e)
        print("=================================\n")
        raise
