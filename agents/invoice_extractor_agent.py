# agents/invoice_extractor_agent.py
import os
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_groq import ChatGroq
from schemas.invoice import InvoiceModel
from dotenv import load_dotenv
load_dotenv()

# Build LLM wrapper
def load_llm():
    groq_key = os.getenv("GROQ_API_KEY")
    model_name = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
    try:
        return ChatGroq(temperature=0, groq_api_key=groq_key, model_name=model_name)
    except Exception:
        return None

llm = load_llm()
parser = PydanticOutputParser(pydantic_object=InvoiceModel)

prompt = ChatPromptTemplate.from_messages([
    ("system",
     "You are a highly accurate, hallucination-free INVOICE extraction model.\n"
     "Your job is to convert messy OCR text — even corrupted, partially unreadable, or noisy — "
     "into a clean JSON structure following the provided schema.\n\n"

     "⚠️ STRICT EXTRACTION RULES — NEVER BREAK THESE:\n"
     "1. NEVER hallucinate, guess, or fabricate any value.\n"
     "   - If a field is missing → return null.\n"
     "   - If text is corrupted → return the corrupted text EXACTLY as seen.\n"
     "   - If numeric fields are corrupted (e.g., '67@89', '?84.4&'), return them AS STRING.\n\n"

     "2. NEVER clean, fix, or standardize corrupted values.\n"
     "   Examples:\n"
     "     'Bt23r' MUST stay 'Bt23r'\n"
     "     'INVQL10' MUST stay 'INVQL10'\n"
     "     '€D kg' → quantity='€D', unit='kg'\n"
     "     'NVAL@139' → total_price='NVAL@139'\n\n"

     "3. DO NOT infer vendor name, invoice number, dates, totals, or item names unless the OCR text "
     "contains a CLEAR, EXACT value.\n"
     "   - If unsure → return null.\n"
     "   - NEVER fill values with unrelated known data.\n\n"

     "4. Items parsing rules:\n"
     "   - Extract each row exactly as seen.\n"
     "   - quantity → numeric ONLY if purely numeric; else null.\n"
     "   - unit_price → numeric ONLY if purely numeric; else string/null.\n"
     "   - line_total → numeric ONLY if clean; else string/null.\n"
     "   - material_name must NEVER be invented or corrected.\n\n"

     "5. Dates:\n"
     "   - If corrupted or mixed characters → return raw text as string.\n"
     "   - Do NOT convert formats unless fully valid.\n\n"

     "6. ALWAYS return valid JSON. NO markdown, NO commentary, NO ```json.\n"
     "   ONLY return the JSON object.\n\n"
    ),

    ("user",
     "OCR TEXT:\n{invoice_text}\n\n"
     "Now extract ALL possible fields into JSON following this schema STRICTLY:\n\n"
     "{format_instructions}\n\n"

     "Extraction requirements:\n"
     "- invoice_no → extract exact invoice number text.\n"
     "- vendor → extract the vendor name exactly.\n"
     "- invoice_created_date → use raw OCR date (even if corrupted).\n"
     "- payment_terms → extract raw text.\n"
     "- items → extract EVERY row with material_name, quantity, unit, unit_price, line_total.\n"
     "- tax_amount → extract number or corrupted string.\n"
     "- total_price → extract number or corrupted string.\n\n"

     "REMEMBER:\n"
     "- NO invented values.\n"
     "- NO interpretation.\n"
     "- NO normalization.\n"
     "- If unreadable → set to null.\n\n"
    )
])


def llm_parse_text_to_invoice(raw_text: str):
    """
    Return parsed InvoiceModel using LLM.
    If LLM fails, print the full error so user can fix extraction.
    """
    raw_text = "" if raw_text is None else str(raw_text)

    # Debug: show OCR text
    print("\n================ OCR RAW TEXT ================")
    print(raw_text)
    print("==============================================\n")

    # Build prompt
    formatted = prompt.format_messages(
        invoice_text=raw_text,
        format_instructions=parser.get_format_instructions()
    )

    # Debug: show formatted prompt
    print("\n================ PROMPT TO LLM ================")
    print(formatted)
    print("==============================================\n")

    # If LLM not loaded → fallback
    if llm is None:
        print("\n[WARNING] LLM not loaded! Using fallback parser.\n")
        from agents.simple_text_parser import quick_parse_invoice_text
        return quick_parse_invoice_text(raw_text)

    # Invoke LLM
    try:
        res = llm.invoke(formatted)
        text = getattr(res, "content", None) or getattr(res, "text", "")

        # Debug: show raw LLM output
        print("\n================ LLM RAW OUTPUT ================")
        print(text)
        print("===============================================\n")

        # Clean unwanted markdown
        if "```" in text:
            text = text.replace("```json", "").replace("```", "").strip()

        # Parse JSON using Pydantic
        return parser.parse(text)

    except Exception as e:
        # Debug: show EXACT reason of failure
        print("\n================ LLM PARSE ERROR ================")
        print("ERROR:", e)
        print("=================================================\n")
        raise  # IMPORTANT: do NOT fallback silently
