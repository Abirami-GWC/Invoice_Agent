# services/ocr_extraction.py

import pytesseract

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

import io
import numpy as np
from typing import Optional
from PIL import Image, ImageOps, ImageFilter

# Optional imports
try:
    import pytesseract
except ImportError:
    pytesseract = None

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

try:
    from pdf2image import convert_from_bytes
except ImportError:
    convert_from_bytes = None


# -----------------------------------------------
# Utility: Deskew image using numpy + PIL
# -----------------------------------------------
def deskew_image(img: Image.Image) -> Image.Image:
    try:
        import cv2
        import numpy as np

        # Convert PIL → OpenCV
        cv_img = np.array(img)
        gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)

        # Threshold to find skew angle
        _, th = cv2.threshold(gray, 0, 255,
                              cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        coords = np.column_stack(np.where(th > 0))
        angle = cv2.minAreaRect(coords)[-1]

        # Correct weird OpenCV angles
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle

        # Rotate
        (h, w) = cv_img.shape[:2]
        M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
        rotated = cv2.warpAffine(cv_img, M, (w, h),
                                 flags=cv2.INTER_CUBIC,
                                 borderMode=cv2.BORDER_REPLICATE)

        return Image.fromarray(rotated)

    except Exception:
        return img  # If deskew fails, just return original


# -----------------------------------------------
# OCR with preprocessing
# -----------------------------------------------
def ocr_image(img: Image.Image) -> str:
    if pytesseract is None:
        print("WARNING: pytesseract not installed.")
        return ""

    # Convert to grayscale
    gray = ImageOps.grayscale(img)

    # Slight sharpen to improve OCR clarity
    gray = gray.filter(ImageFilter.SHARPEN)

    # Adaptive thresholding (convert to pure black/white)
    gray = gray.point(lambda x: 0 if x < 150 else 255)

    # Deskew image (optional but boosts accuracy)
    gray = deskew_image(gray)

    try:
        text = pytesseract.image_to_string(gray)
        return text.strip()
    except Exception as e:
        print("OCR ERROR:", e)
        return ""


# -----------------------------------------------
# PDF → text (fastest) using PyPDF
# -----------------------------------------------
def extract_pdf_text(pdf_bytes: bytes) -> str:
    if PdfReader is None:
        return ""

    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        texts = []
        for page in reader.pages:
            try:
                t = page.extract_text() or ""
            except Exception:
                t = ""
            texts.append(t)
        return "\n".join(texts).strip()
    except Exception as e:
        print("PDF TEXT ERROR:", e)
        return ""


# -----------------------------------------------
# PDF → first page image (fallback)
# -----------------------------------------------
def pdf_to_image(pdf_bytes: bytes) -> Optional[bytes]:
    if convert_from_bytes is None:
        return None
    try:
        pages = convert_from_bytes(pdf_bytes, dpi=300, first_page=1, last_page=1)
        if not pages:
            return None
        buf = io.BytesIO()
        pages[0].save(buf, format="PNG")
        return buf.getvalue()
    except Exception as e:
        print("PDF → PNG ERROR:", e)
        return None


# -----------------------------------------------
# MAIN FUNCTION — BEST OCR EXTRACTOR
# -----------------------------------------------
def extract_text(input_bytes: bytes, content_type: Optional[str] = None) -> str:
    """
    Best effort extraction:
      1. PDF direct text
      2. PDF OCR fallback
      3. Image OCR with preprocessing
      4. Raw UTF-8 decode
    """
    if not input_bytes:
        return ""

    ct = (content_type or "").lower()

    # Detect PDF by header OR content type
    is_pdf = ("%pdf" in input_bytes[:10].lower().decode(errors="ignore")) or ("pdf" in ct)

    # ----------- 1) Direct PDF text (best) -----------
    if is_pdf:
        txt = extract_pdf_text(input_bytes)
        if txt:
            print("✔ PDF direct extraction successful")
            return txt

        # ----------- 2) PDF → image → OCR -----------
        png = pdf_to_image(input_bytes)
        if png:
            print("✔ PDF converted to image for OCR")
            try:
                img = Image.open(io.BytesIO(png))
                return ocr_image(img)
            except Exception:
                pass

        return ""

    # ----------- 3) Image OCR -----------
    try:
        img = Image.open(io.BytesIO(input_bytes))
        print("✔ Image detected — using OCR")
        return ocr_image(img)
    except Exception:
        pass

    # ----------- 4) Fallback: raw text decode -----------
    try:
        return input_bytes.decode("utf-8", errors="ignore").strip()
    except Exception:
        return ""
