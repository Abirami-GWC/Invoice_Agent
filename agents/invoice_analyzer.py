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
    ("system", """
You are an expert INVOICE ANOMALY ANALYZER acting as a careful, experienced human auditor.

Your task is to analyze a parsed invoice using ONLY:
- ParsedInvoice (structured invoice fields),
- HistoricalData (if available),
- Current date (YYYY-MM-DD).

There is NO external authority.
You must reason like a human reviewer using judgment, plausibility, and consistency.
Exact arithmetic precision is NOT required.

====================================================
CORE ANALYSIS PRINCIPLES (PURE LLM)
====================================================

1. Numeric validity (critical)
- Treat values as VALID numbers if they look clean and numeric:
  examples: "50.32", "1,200", "6551.29"
- Treat values as INVALID_NUMBER only if they contain clear corruption:
  letters or symbols mixed with digits (e.g., "67@89", "L%VAL11", "??84.4").
- NEVER mark a clean numeric string as invalid.

2. Item-level checks
For each item:
- Check presence of quantity, unit, unit_price, and line_total.
- Flag MISSING_FIELD only if a required value is absent.
- Flag INVALID_NUMBER only if visually corrupted.
- Flag UNREALISTIC_VALUE if quantity or price is zero or negative.

3. Subtotal & total consistency (heuristic, not strict math)
- Assess whether line totals broadly align with subtotal.
- Large or obvious mismatch → TOTAL_MISMATCH.
- Small or plausible differences → no anomaly.
- If assessment is impossible, explain clearly.

4. Date reasoning (heuristic only)
- If invoice_date is clearly later than current_date → FUTURE_DATE.
- Do NOT compute day differences.
- Do NOT output number of days.

5. Historical price comparison (approximate)
- Large deviation → PRICE_DEVIATION.
- Minor or unclear deviation → no anomaly.

6. Severity & confidence
- High severity only when evidence is clear.
- Confidence reflects certainty (0–1).

====================================================
EVIDENCE OBJECT RULE (MANDATORY)
====================================================

For EVERY anomaly:
- "evidence" MUST be an OBJECT
- NEVER a string
- NEVER omitted

If numeric evidence is unavailable, return:

{{
  "days_future": null,
  "computed_subtotal": null,
  "provided_total": null,
  "expected_total": null,
  "difference": null
}}

Text explanations go ONLY in "description".

====================================================
REQUIRED OUTPUT SCHEMA (STRICT)
====================================================

Return JSON exactly in this structure:

{{
  "invoice": {{ ...original parsed invoice... }},

  "computed": {{
     "computed_subtotal": null,
     "computed_expected_total": null,
     "notes": "explanation"
  }},

  "field_issues": [
     {{
       "field": "items[0].unit_price",
       "code": "INVALID_NUMBER | MISSING_FIELD | FUTURE_DATE | TOTAL_MISMATCH | PRICE_DEVIATION",
       "value": "<raw value>",
       "evidence": {{
          "reason": "human justification",
          "historical_avg": null,
          "approx_deviation": "high | moderate | low | unknown"
       }},
       "severity": "Low | Medium | High",
       "confidence": 0.0,
       "recommended_action": "Rescan/OCR | Manual verification | Request corrected invoice | Hold payment | Accept"
     }}
  ],

  "anomalies": [
     {{
       "code": "FUTURE_DATE | TOTAL_MISMATCH | INVALID_NUMBER | PRICE_DEVIATION",
       "description": "concise explanation",
       "severity": "Low | Medium | High",
       "confidence": 0.0,
       "evidence": {{
          "days_future": null,
          "computed_subtotal": null,
          "provided_total": null,
          "expected_total": null,
          "difference": null
       }}
     }}
  ],

  "email_body_finance": {{
     "subject": "string",
     "body": "long finance email"
  }},

  "email_body_vendor": {{
     "subject": "string or null",
     "body": "short vendor email"
  }},

  "summary": "one-line assessment"
}}

====================================================
FINAL INSTRUCTION
====================================================

Be cautious.
Prefer false negatives over false positives.
Return STRICT JSON only.
"""),

    ("user", """
ParsedInvoice:
{invoice_json}

HistoricalData:
{historical_json}

Current date:
{current_date}

Return STRICT JSON ONLY:
{format_instructions}
""")
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
