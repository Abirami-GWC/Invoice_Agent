
# models/gemini_model_loader.py
import os
from dotenv import load_dotenv
load_dotenv()

def load_gemini_llm():
    try:
        from google import genai
        key = os.getenv("GEMINI_API_KEY")
        if not key:
            return None
        client = genai.Client(api_key=key)
        # Provide a minimal wrapper with `invoke(prompt)` returning object with .content
        class _Wrapper:
            def __init__(self, client):
                self.client = client
            def invoke(self, prompt: str):
                # use responses.create if available
                try:
                    resp = self.client.responses.create(model=os.getenv("GEMINI_MODEL","models/gemini-2.0-flash-lite"), input=prompt)
                    class R: pass
                    r = R()
                    r.content = getattr(resp, 'output_text', None) or str(resp)
                    return r
                except Exception:
                    class R: pass
                    r = R()
                    r.content = ""
                    return r
        return _Wrapper(client)
    except Exception:
        return None
