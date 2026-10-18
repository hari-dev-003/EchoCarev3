"""Turns uploaded documents into Gemini Vision inputs or text/OCR fallback."""
import io

try:
    import pymupdf as fitz
except ImportError:
    import fitz
from PIL import Image

MIME = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}


def to_vision_parts(data: bytes, filename: str, max_pages=4, dpi=130):
    ext = filename.lower().rsplit(".", 1)[-1]
    if ext == "pdf":
        parts = []
        with fitz.open(stream=data, filetype="pdf") as doc:
            for i, page in enumerate(doc):
                if i >= max_pages:
                    break
                parts.append((page.get_pixmap(dpi=dpi).tobytes("png"), "image/png"))
        return parts
    return [(data, MIME.get(ext, "image/jpeg"))]


def extract_text(data: bytes, filename: str) -> tuple[str, str]:
    is_pdf = filename.lower().endswith(".pdf")
    if is_pdf:
        with fitz.open(stream=data, filetype="pdf") as doc:
            text = "".join(p.get_text() for p in doc).strip()
        if len(text) >= 40:
            return text, "pymupdf"
    return _ocr(data, is_pdf), "ocr"


def _ocr(data: bytes, is_pdf: bool) -> str:
    try:
        import pytesseract
        if is_pdf:
            out = ""
            with fitz.open(stream=data, filetype="pdf") as doc:
                for p in doc:
                    out += pytesseract.image_to_string(Image.open(io.BytesIO(p.get_pixmap(dpi=250).tobytes("png")))) + "\n"
            return out.strip()
        return pytesseract.image_to_string(Image.open(io.BytesIO(data))).strip()
    except Exception:
        return ""
