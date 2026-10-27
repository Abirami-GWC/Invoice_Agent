from services.extractor import extract_text
from agents.invoice_extractor_agent import invoice_extractor_agent

# Test file path
FILE_PATH = "debug/img.png"   # change if needed

# Load file
with open(FILE_PATH, "rb") as f:
    data = f.read()

# Run OCR
text = extract_text(data, content_type="image/png")

print("\n=== OCR TEXT ===\n")
print(text)
print("\n================\n")

# Only proceed if OCR worked
if not text.strip():
    print("❌ OCR returned EMPTY text — cannot continue.")
    exit()

# Parse via LLM
parsed = invoice_extractor_agent(text)

print("\n=== PARSED JSON ===\n")
print(parsed.model_dump())
