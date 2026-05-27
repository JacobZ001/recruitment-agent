#!/usr/bin/env python3
"""
Seed a deterministic testing candidate by ingesting a PDF CV into the local slice.

Requires ``LLM_PROVIDER=stub`` (or a configured provider) for scoring-context materialization
and CV parse/score. Uses the repo SQLite DB at ``data/app.db`` by default.

Example:
  python scripts/seed_testing_candidate_from_pdf.py
  python scripts/seed_testing_candidate_from_pdf.py --pdf "%USERPROFILE%\\Desktop\\candidate_cv.pdf"
"""

from __future__ import annotations

import argparse
import base64
import os
import sys
from pathlib import Path
from uuid import UUID, uuid5

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("LLM_PROVIDER", "stub")
os.environ.setdefault("LLM_MODEL", "stub-cv")

from modules.recruitment.fixtures import TESTING_DESKTOP_CANDIDATE_ID  # noqa: E402
from modules.recruitment.runtime import VerticalSliceApiRuntime  # noqa: E402
from modules.recruitment.use_cases import (  # noqa: E402
    author_job_context_from_text,
    author_organization_context_from_text,
    author_recruiter_actor_context_from_text,
    publish_recruitment_event,
    refresh_active_scoring_context,
    submit_cv_pdf,
)
from skills.llm.llm_provider import StubLLMProvider  # noqa: E402
from skills.llm.scoring_context_materialize_from_prose import (  # noqa: E402
    ScoringContextMaterializeFromProseSkill,
)

_DEFAULT_PDF = ROOT / "fixtures" / "candidate_cv.pdf"
_DESKTOP_PDF = Path.home() / "Desktop" / "candidate_cv.pdf"


def _establish_ready_scoring_context(runtime: VerticalSliceApiRuntime) -> None:
    author_organization_context_from_text(
        runtime,
        (
            "BlueOcean is a recruitment company and the Talent Ops team operates in a "
            "fast-moving recruiter workflow. The organization values clear communication "
            "and structured follow-through."
        ),
        source_ref="seed://organization",
    )
    author_recruiter_actor_context_from_text(
        runtime,
        (
            "Recruiter test-recruiter is a lead recruiter focused on operator-ready execution. "
            "The recruiter values stakeholder communication and ownership, and avoids "
            "unclear communication."
        ),
        source_ref="seed://recruiter",
    )
    author_job_context_from_text(
        runtime,
        (
            "We are hiring for a Recruiting Operations Specialist. Must-have signals include "
            "recruiter coordination, stakeholder communication, and process ownership. "
            "Preferred signals include ATS familiarity and reporting discipline. Success in "
            "the role means keeping the hiring workflow organized and surfacing risks early. "
            "Responsibilities include coordinating candidate flow and maintaining process hygiene."
        ),
        source_ref="seed://job_text",
    )
    refresh_active_scoring_context(
        runtime,
        materializer=ScoringContextMaterializeFromProseSkill(provider=StubLLMProvider()),
    )


def seed_testing_candidate_from_pdf(
    *,
    pdf_path: Path,
    candidate_id: UUID = TESTING_DESKTOP_CANDIDATE_ID,
    db_path: str | None = "data/app.db",
) -> UUID:
    pdf_bytes = pdf_path.read_bytes()
    pdf_b64 = base64.b64encode(pdf_bytes).decode("ascii")

    runtime = VerticalSliceApiRuntime(db_path=db_path)
    _establish_ready_scoring_context(runtime)
    publish_recruitment_event(runtime, candidate_id, "candidate_created", {"source": "pdf_seed"})
    result = submit_cv_pdf(runtime, candidate_id, pdf_b64, file_name=pdf_path.name)
    if not result.ingress_accepted:
        raise RuntimeError(f"cv ingress not accepted: {result.publish_status}")

    got = runtime.bundle.store.get_for_candidate(candidate_id)
    if not got.ok or got.snapshot is None:
        raise RuntimeError("candidate snapshot missing after ingest")
    snap = got.snapshot
    prof = snap.ingress_profile
    summary = prof.summary[:120] if prof and prof.summary else "(no profile summary)"
    light = snap.evaluation.light.normalized_score if snap.evaluation and snap.evaluation.light else None
    print(f"candidate_id={candidate_id}")
    print(f"pipeline_phase={snap.pipeline.phase.value}")
    print(f"profile_summary={summary!r}")
    print(f"light_score={light}")
    print("Open recruiter UI: /app/ then search or open this candidate id in the list.")
    return candidate_id


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed testing candidate from PDF CV")
    parser.add_argument(
        "--pdf",
        type=Path,
        default=_DEFAULT_PDF if _DEFAULT_PDF.is_file() else _DESKTOP_PDF,
        help="Path to candidate PDF (default: fixtures/candidate_cv.pdf or Desktop copy)",
    )
    parser.add_argument(
        "--candidate-id",
        type=UUID,
        default=TESTING_DESKTOP_CANDIDATE_ID,
        help="Stable candidate UUID (default: deterministic testing id)",
    )
    parser.add_argument(
        "--db-path",
        default="data/app.db",
        help="SQLite path (default: data/app.db). Use empty string for in-memory.",
    )
    args = parser.parse_args()
    if not args.pdf.is_file():
        raise SystemExit(f"PDF not found: {args.pdf}")
    db = args.db_path.strip() or None
    seed_testing_candidate_from_pdf(
        pdf_path=args.pdf,
        candidate_id=args.candidate_id,
        db_path=db,
    )


if __name__ == "__main__":
    main()
