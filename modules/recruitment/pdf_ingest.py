"""
Deterministic PDF CV ingress helpers.

These functions live at the application boundary so HTTP handlers can stay thin
while orchestration continues to consume plain ``cv_text`` only.
"""

from __future__ import annotations

import base64
import binascii
import io
from dataclasses import dataclass

from pypdf import PdfReader

from .exceptions import InvalidCvPdfError

_MAX_PDF_BYTES = 5_000_000
_MAX_PDF_PAGES = 8
_MAX_EXTRACTED_TEXT_CHARS = 20_000
_DEFAULT_FILE_NAME = "cv.pdf"


def _normalize_text(raw: str) -> str:
    lines = [" ".join(line.split()) for line in raw.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def _validated_file_name(file_name: str | None) -> str:
    candidate = (file_name or _DEFAULT_FILE_NAME).strip()
    if not candidate:
        raise InvalidCvPdfError("file_name must be non-empty")
    if not candidate.lower().endswith(".pdf"):
        raise InvalidCvPdfError("file_name must end with .pdf")
    return candidate


def decode_pdf_base64(pdf_base64: str, *, file_name: str | None = None) -> bytes:
    validated_name = _validated_file_name(file_name)
    payload = pdf_base64.strip()
    if not payload:
        raise InvalidCvPdfError("pdf_base64 must be non-empty")
    try:
        pdf_bytes = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise InvalidCvPdfError(
            f"{validated_name}: pdf_base64 must be valid base64-encoded PDF bytes"
        ) from exc
    if not pdf_bytes:
        raise InvalidCvPdfError(f"{validated_name}: decoded PDF bytes are empty")
    if len(pdf_bytes) > _MAX_PDF_BYTES:
        raise InvalidCvPdfError(
            f"{validated_name}: PDF exceeds byte limit ({_MAX_PDF_BYTES} bytes)"
        )
    if not pdf_bytes.startswith(b"%PDF-"):
        raise InvalidCvPdfError(f"{validated_name}: payload is not a valid PDF file")
    return pdf_bytes


@dataclass(frozen=True)
class ExtractedPdfCv:
    file_name: str
    byte_length: int
    page_count: int
    cv_text: str


def extract_text_from_pdf_bytes(
    pdf_bytes: bytes,
    *,
    file_name: str | None = None,
) -> ExtractedPdfCv:
    validated_name = _validated_file_name(file_name)
    if not pdf_bytes:
        raise InvalidCvPdfError(f"{validated_name}: decoded PDF bytes are empty")
    if len(pdf_bytes) > _MAX_PDF_BYTES:
        raise InvalidCvPdfError(
            f"{validated_name}: PDF exceeds byte limit ({_MAX_PDF_BYTES} bytes)"
        )
    if not pdf_bytes.startswith(b"%PDF-"):
        raise InvalidCvPdfError(f"{validated_name}: payload is not a valid PDF file")

    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
    except Exception as exc:
        raise InvalidCvPdfError(f"{validated_name}: failed to parse PDF") from exc

    page_count = len(reader.pages)
    if page_count < 1:
        raise InvalidCvPdfError(f"{validated_name}: PDF has no pages")
    if page_count > _MAX_PDF_PAGES:
        raise InvalidCvPdfError(
            f"{validated_name}: PDF exceeds page limit ({_MAX_PDF_PAGES} pages)"
        )

    fragments: list[str] = []
    for page_idx, page in enumerate(reader.pages, start=1):
        try:
            extracted = page.extract_text() or ""
        except Exception as exc:
            raise InvalidCvPdfError(
                f"{validated_name}: failed to extract text from page {page_idx}"
            ) from exc
        if extracted:
            fragments.append(extracted)

    cv_text = _normalize_text("\n".join(fragments))
    if not cv_text:
        raise InvalidCvPdfError(f"{validated_name}: PDF text extraction produced empty text")
    if len(cv_text) > _MAX_EXTRACTED_TEXT_CHARS:
        raise InvalidCvPdfError(
            f"{validated_name}: extracted text exceeds character limit "
            f"({_MAX_EXTRACTED_TEXT_CHARS} chars)"
        )
    return ExtractedPdfCv(
        file_name=validated_name,
        byte_length=len(pdf_bytes),
        page_count=page_count,
        cv_text=cv_text,
    )
