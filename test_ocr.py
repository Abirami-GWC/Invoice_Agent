# # test_ocr.py
# import sys
# from pathlib import Path
# from services.ocr_extractor import extract_text

# def load_bytes(path: Path) -> bytes:
#     return path.read_bytes()

# def main():
#     if len(sys.argv) < 2:
#         print("Usage: python test_ocr.py <path-to-file.pdf|png|jpg>")
#         return

#     p = Path(sys.argv[1])
#     if not p.exists():
#         print("File not found:", p)
#         return

#     content_type = ""
#     if p.suffix.lower() == ".pdf":
#         content_type = "application/pdf"
#     elif p.suffix.lower() in (".png", ".jpg", ".jpeg"):
#         content_type = "image/" + p.suffix.lower().lstrip(".")
#     else:
#         content_type = ""

#     b = load_bytes(p)
#     text = extract_text(b, content_type)
#     print("\n=== EXTRACTED TEXT ===\n")
#     print(text)
#     print("\n=== END ===\n")

# if __name__ == "__main__":
#     main()

import sys
from pathlib import Path
from services.ocr_extractor import extract_text
from services.invoice_parser import parse_invoice
import json


def load_bytes(path: Path) -> bytes:
    return path.read_bytes()


def detect_content_type(p: Path) -> str:
    ext = p.suffix.lower()
    if ext == ".pdf":
        return "application/pdf"
    elif ext in (".png", ".jpg", ".jpeg"):
        return "image/" + ext.lstrip(".")
    return ""


def main():
    if len(sys.argv) < 2:
        print("Usage: python test_ocr.py <path-to-file.pdf|png|jpg>")
        return

    p = Path(sys.argv[1])
    if not p.exists():
        print("❌ File not found:", p)
        return

    print("📄 Processing:", p)

    content_type = detect_content_type(p)
    b = load_bytes(p)

    # STEP 1: OCR - Extract raw text
    print("\n=== STEP 1: OCR TEXT EXTRACTION ===")
    text = extract_text(b, content_type)
    print(text)

    # STEP 2: Convert text → Structured Invoice JSON
    print("\n=== STEP 2: PARSED STRUCTURED INVOICE DATA ===")
    invoice_data = parse_invoice(text)

    # Pretty JSON output
    print(json.dumps(invoice_data, indent=4))
    print("\n=== END ===")


if __name__ == "__main__":
    main()
