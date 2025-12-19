## File: `models/groq_model_loader.py` and `models/gemini_model_loader.py` (stubs)

# models/groq_model_loader.py
import os
from dotenv import load_dotenv
load_dotenv()

def load_groq_llm():
    try:
        from langchain_groq import ChatGroq
        key = os.getenv("GROQ_API_KEY")
        if not key:
            return None
        return ChatGroq(temperature=0, groq_api_key=key, model_name=os.getenv("GROQ_MODEL","llama-3.1-8b-instant"))
    except Exception:
        return None
