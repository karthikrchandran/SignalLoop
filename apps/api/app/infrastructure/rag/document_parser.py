"""Document parsing helpers for knowledge ingestion."""

from __future__ import annotations

from io import BytesIO

import chardet

MAX_DOCUMENT_BYTES = 20 * 1024 * 1024
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt"}


def validate_document_upload(filename: str, size_bytes: int) -> None:
    """Validate document type and size."""
    extension = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError("Unsupported document type")
    if size_bytes > MAX_DOCUMENT_BYTES:
        raise ValueError("Document exceeds 20 MB limit")


def parse_txt(data: bytes) -> str:
    """Safely decode text bytes."""
    detection = chardet.detect(data)
    encoding = detection.get("encoding") or "utf-8"
    return data.decode(encoding, errors="replace")


def parse_pdf(data: bytes) -> str:
    """Extract text from PDF bytes using PyPDF2."""
    try:
        from PyPDF2 import PdfReader
    except ImportError as exc:
        raise RuntimeError("PyPDF2 is required for PDF parsing") from exc

    reader = PdfReader(BytesIO(data))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def parse_docx(data: bytes) -> str:
    """Extract text from DOCX bytes using python-docx."""
    try:
        from docx import Document
    except ImportError as exc:
        raise RuntimeError("python-docx is required for DOCX parsing") from exc

    document = Document(BytesIO(data))
    return "\n".join(paragraph.text for paragraph in document.paragraphs)


def parse_document(filename: str, data: bytes) -> str:
    """Parse supported document bytes into text."""
    validate_document_upload(filename, len(data))
    extension = "." + filename.rsplit(".", 1)[-1].lower()
    if extension == ".pdf":
        return parse_pdf(data)
    if extension == ".docx":
        return parse_docx(data)
    return parse_txt(data)
