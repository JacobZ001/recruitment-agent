"""PDF CV ingestion via submit_cv_pdf."""

from __future__ import annotations

import base64
from uuid import uuid4

import pytest

from modules.recruitment.exceptions import InvalidCvPdfError
from modules.recruitment.runtime import VerticalSliceApiRuntime
from modules.recruitment.use_cases import submit_cv_pdf
from schemas.state_schema import PipelinePhase


def _build_pdf_bytes(text: str | None) -> bytes:
    if text is None:
        stream = b"BT\nET"
    else:
        safe = (
            text.replace("\\", "\\\\")
            .replace("(", "\\(")
            .replace(")", "\\)")
        )
        stream = f"BT\n/F1 12 Tf\n72 720 Td\n({safe}) Tj\nET".encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for idx, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out.extend(f"{idx} 0 obj\n".encode())
        out.extend(obj)
        out.extend(b"\nendobj\n")
    xref_offset = len(out)
    out.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    out.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        out.extend(f"{offset:010d} 00000 n \n".encode())
    out.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode()
    )
    return bytes(out)


def _build_pdf_base64(text: str | None) -> str:
    return base64.b64encode(_build_pdf_bytes(text)).decode("ascii")


def test_submit_cv_pdf_persists_typed_snapshot_fields(establish_ready_scoring_context) -> None:
    rt = VerticalSliceApiRuntime()
    establish_ready_scoring_context(rt)
    cid = uuid4()
    result = submit_cv_pdf(
        rt,
        cid,
        _build_pdf_base64("Senior Python developer with 8 years of experience"),
        file_name="candidate_cv.pdf",
    )
    assert result.ingress_accepted is True

    got = rt.bundle.store.get_for_candidate(cid)
    assert got.ok and got.snapshot is not None
    snap = got.snapshot
    assert snap.pipeline.phase == PipelinePhase.QUESTIONNAIRE_PENDING
    got_c = rt.candidate_store.get(cid)
    assert got_c.ok and got_c.candidate is not None
    evaluation = got_c.candidate.evaluation_status
    assert evaluation.light is not None
    assert "Senior Python developer" in (got_c.candidate.profile.summary or "")
    assert evaluation.light.normalized_score is not None
    assert snap.evaluation_status_ref is not None


def test_submit_cv_pdf_empty_text_extraction_raises() -> None:
    rt = VerticalSliceApiRuntime()
    cid = uuid4()
    with pytest.raises(InvalidCvPdfError, match="empty text"):
        submit_cv_pdf(
            rt,
            cid,
            _build_pdf_base64(None),
            file_name="blank_cv.pdf",
        )
