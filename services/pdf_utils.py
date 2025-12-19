# services/pdf_utils.py
import io
from typing import Optional
try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None

try:
    from pdf2image import convert_from_bytes
except Exception:
    convert_from_bytes = None

from PIL import Image  # pillow required

def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    """
    Try to extract text directly from PDF bytes using pypdf.
    Returns text or empty string on failure.
    """
    if PdfReader is None:
        return ""

    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        texts = []
        for p in reader.pages:
            try:
                t = p.extract_text() or ""
            except Exception:
                t = ""
            if t:
                texts.append(t)
        return "\n".join(texts).strip()
    except Exception as e:
        # Debug message for caller
        print("PDF TEXT ERROR:", e)
        return ""

def pdf_first_page_to_png_bytes(pdf_bytes: bytes, dpi: int = 300) -> Optional[bytes]:
    """
    Convert the first page of a PDF into PNG bytes using pdf2image/poppler.
    Returns PNG bytes or None on failure.
    """
    if convert_from_bytes is None:
        print("pdf2image not installed or poppler not available.")
        return None
    try:
        pages = convert_from_bytes(pdf_bytes, dpi=dpi, first_page=1, last_page=1, fmt="png")
        if not pages:
            return None
        img = pages[0]
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception as e:
        print("PDF→PNG ERROR:", e)
        return None
