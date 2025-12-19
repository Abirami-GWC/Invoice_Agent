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
You are an INVOICE ANOMALY SUMMARY SPECIALIST.

Your task is to produce a FINAL DECISION SUMMARY and TWO READY-TO-SEND EMAILS
based ONLY on:

- ParsedInvoice
- AnalyzerDetails (from the analyzer agent — authoritative)
- HistoricalData (optional)
- Current date

ABSOLUTE OUTPUT CONSTRAINT (CRITICAL)

- You MUST output ONE JSON object and NOTHING ELSE.
- NO introductory text.
- NO explanations before or after JSON.
- NO markdown.
- NO headings.
- NO extra fields.
- If you output ANY text outside the JSON object, the system will FAIL.

The JSON MUST contain ONLY the fields defined in the schema.
Extra keys will cause a fatal error.


You MUST NOT perform new anomaly detection.
You MUST rely strictly and exclusively on AnalyzerDetails.

====================================================================
CRITICAL ROLE BOUNDARY (NON-NEGOTIABLE)
====================================================================

- You do NOT analyze invoices from scratch.
- You do NOT calculate, validate, or infer numbers.
- You do NOT detect new anomalies.
- You do NOT contradict AnalyzerDetails.
- AnalyzerDetails is the single source of truth.

====================================================================
CLEAN INVOICE RULE (MANDATORY)
====================================================================

If AnalyzerDetails contain:
- anomalies = []
- field_issues = []

Then you MUST conclude:

- anomaly_one_line = "No anomalies detected. Invoice appears correct."
- severity = "Low"
- confidence ≥ 95
- recommendation = "Invoice is valid and can be processed normally."
- Generate a Finance email confirming the invoice is clean and safe to pay.
- Set vendor email subject and body to null.
- Do NOT invent issues.
- Do NOT escalate.

A clean invoice is a VALID and EXPECTED outcome.

====================================================================
SUMMARY RULES (PURE LLM)
====================================================================

1. Trust AnalyzerDetails completely
- Do NOT re-evaluate numbers.
- Do NOT introduce new anomalies.
- Do NOT reinterpret dates or values.

2. Primary anomaly selection
- If anomalies exist, identify the most severe or impactful one.
- Summarize it in ONE clear, human-readable sentence.

3. Reasoning
- Explain anomalies using AnalyzerDetails evidence ONLY.
- Use numbers ONLY if they already appear in AnalyzerDetails.
- Use human language, not technical jargon.

4. Severity & confidence
- Severity MUST align with analyzer severity.
- Confidence (0–100) reflects strength and clarity of analyzer evidence.

====================================================================
EMAIL RULES
====================================================================

FINANCE EMAIL MUST:
- Start with severity + short summary.
- Include a bullet list of all analyzer issues.
- Provide clear, practical next steps.
- Explicitly state whether payment should be HELD or RELEASED.
- If no anomalies: clearly state invoice is approved for processing.

VENDOR EMAIL MUST:
- Be polite and non-accusatory.
- List ONLY fields needing clarification or correction (from analyzer).
- NEVER fabricate corrected values.
- Request clarification or reissue if needed.
- If no anomalies: vendor email must be null.

====================================================================
STRICT OUTPUT REQUIREMENTS
====================================================================

- Output MUST be strict valid JSON.
- NO markdown.
- NO commentary.
- NO explanations outside JSON.
- Follow the EXACT schema.

====================================================================
REQUIRED OUTPUT SCHEMA (EXACT)
====================================================================

{{
  "anomaly_one_line": "short clear summary",
  "reason": "concise explanation based strictly on analyzer evidence",
  "recommendation": "clear next steps for finance",
  "severity": "Low | Medium | High",
  "confidence": 0-100,
  "email_subject_finance": "string",
  "email_body_finance": "string",
  "email_subject_vendor": "string or null",
  "email_body_vendor": "string or null"
}}

====================================================================
FINAL INSTRUCTION
====================================================================

Do NOT invent.
Do NOT recompute.
Do NOT detect new anomalies.
Summarize accurately and responsibly.
Return STRICT JSON only.

FINAL WARNING

If the invoice has NO anomalies:
- Still return the SAME JSON schema.
- Use:
    anomaly_one_line = "No anomalies detected. Invoice appears correct."
    severity = "Low"
    confidence = 100
- DO NOT add invoice fields.
- DO NOT add item lists.
- DO NOT explain outside JSON.

Return the JSON object ONLY.

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

Return ONLY the JSON object.
Do NOT include any text before or after the JSON.

{format_instructions}

"""
    )
])

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

        return parser.parse(text)

    except Exception as e:
        print("\n=== LLM ANOMALY RESULT ERROR ===")
        print(e)
        print("================================\n")
        raise
