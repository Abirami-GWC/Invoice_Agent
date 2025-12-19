# models/groq_loader.py
import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq

load_dotenv()

def load_llm():
    return ChatGroq(
        model_name="llama-3.1-8b-instant",
        groq_api_key=os.getenv("GROQ_API_KEY"),
        temperature=0
    )
