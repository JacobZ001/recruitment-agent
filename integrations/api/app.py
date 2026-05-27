"""
Thin FastAPI boundary for the recruiter vertical slice.

HTTP concerns only; recruitment business actions live in ``modules.recruitment``.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List, Optional
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from integrations.api.demo_page import build_demo_recruiter_html
from integrations.api.errors import raise_recruitment_http
from integrations.api.schemas_http import (
    AdminResetResponse,
    CandidateActionBody,
    CandidatePdfIngressBody,
    CandidateListItem,
    CandidateViewResponse,
    DemoCandidateResponse,
    DemoRunResponse,
    EventIngressResponse,
    HealthResponse,
    JobContextPdfBody,
    JobContextTextBody,
    OrganizationContextBody,
    RecruiterActorContextBody,
    RecruiterJobAnswersBody,
    ScoringContextResponse,
    StateSummaryResponse,
    TimelineResponse,
    VerticalSliceIngressEventBody,
)
from modules.recruitment.runtime import VerticalSliceApiRuntime
from modules.recruitment import (
    RecruitmentUseCaseError,
    author_job_context_from_pdf,
    author_job_context_from_recruiter_answers,
    author_job_context_from_text,
    author_organization_context_from_text,
    author_recruiter_actor_context_from_text,
    get_active_scoring_context,
    get_candidate_view_for_runtime,
    get_demo_candidate,
    get_state_summary,
    get_state_summary_for_candidate,
    get_timeline_for_candidate,
    policies,
    publish_recruitment_event,
    list_candidates,
    perform_candidate_action,
    record_recruiter_decision,
    refresh_active_scoring_context,
    run_primary_demo_sequence,
    submit_cv_pdf,
)
from modules.recruitment.bootstrap import VERTICAL_SLICE_DEFAULT_CANDIDATE_ID
from runtime.persistence.sqlite_state_store import SQLiteStateStore


def get_runtime(request: Request) -> VerticalSliceApiRuntime:
    rt = getattr(request.app.state, "vertical_slice", None)
    if rt is None:
        raise HTTPException(status_code=503, detail="runtime not initialized")
    return rt


DEFAULT_VERTICAL_SLICE_DB_PATH = "data/app.db"
DEFAULT_ENV_FILE_NAME = ".env"
ENV_FILE_ENV_VAR = "VERTICAL_SLICE_ENV_FILE"
CORS_ORIGINS_ENV_VAR = "VERTICAL_SLICE_CORS_ORIGINS"


def _frontend_dist_dir() -> Optional[Path]:
    """Return ``frontend/dist`` when a production build exists."""
    dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if dist.is_dir() and (dist / "index.html").is_file():
        return dist
    return None


def _configure_cors(app: FastAPI) -> None:
    raw = os.environ.get(CORS_ORIGINS_ENV_VAR, "").strip()
    if not raw:
        return
    origins = [o.strip() for o in raw.split(",") if o.strip()]
    if not origins:
        return
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def _strip_env_value(raw: str) -> str:
    s = raw.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        return s[1:-1]
    return s


def _load_local_env_file(explicit_path: Optional[str] = None) -> Optional[str]:
    """
    Load local environment variables at the API boundary.

    Existing process environment wins. This keeps tests deterministic and avoids
    hidden provider configuration deeper in the stack.
    """
    candidate_paths: List[Path] = []
    raw_explicit = explicit_path if explicit_path is not None else os.environ.get(ENV_FILE_ENV_VAR)
    if raw_explicit:
        candidate_paths.append(Path(raw_explicit))
    repo_root_env = Path(__file__).resolve().parents[2] / DEFAULT_ENV_FILE_NAME
    cwd_env = Path.cwd() / DEFAULT_ENV_FILE_NAME
    for p in (repo_root_env, cwd_env):
        if p not in candidate_paths:
            candidate_paths.append(p)

    target = next((p for p in candidate_paths if p.exists() and p.is_file()), None)
    if target is None:
        return None

    for raw_line in target.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env_key = key.strip()
        if not env_key or env_key in os.environ:
            continue
        os.environ[env_key] = _strip_env_value(value)
    return str(target)


def _resolve_vertical_slice_db_path(explicit: Optional[str]) -> Optional[str]:
    """SQLite file path, or ``None`` for in-memory store."""
    if explicit is not None:
        s = explicit.strip()
        return s if s else None
    raw = os.environ.get("VERTICAL_SLICE_DB_PATH")
    if raw is None:
        return DEFAULT_VERTICAL_SLICE_DB_PATH
    s = raw.strip()
    return None if s == "" else s


def create_app(*, db_path: Optional[str] = None) -> FastAPI:
    def _context_response(rt: VerticalSliceApiRuntime) -> ScoringContextResponse:
        context = get_active_scoring_context(rt)
        if context is None:
            raise HTTPException(status_code=404, detail={"code": "scoring_context_missing"})
        if hasattr(context, "model_dump"):
            payload = context.model_dump(mode="json")
        else:
            payload = context.dict()
        return ScoringContextResponse(**payload)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.loaded_env_file = _load_local_env_file()
        resolved = _resolve_vertical_slice_db_path(db_path)
        if resolved:
            Path(resolved).parent.mkdir(parents=True, exist_ok=True)
            app.state.vertical_slice = VerticalSliceApiRuntime(db_path=resolved)
        else:
            app.state.vertical_slice = VerticalSliceApiRuntime()
        yield

    app = FastAPI(
        title="BlueOcean vertical slice (reference)",
        version="0.1.0",
        lifespan=lifespan,
    )
    _configure_cors(app)

    dist_dir = _frontend_dist_dir()
    if dist_dir is not None:

        @app.get("/", include_in_schema=False)
        def redirect_root_to_app() -> RedirectResponse:
            return RedirectResponse(url="/app/", status_code=307)

        app.mount("/app", StaticFiles(directory=str(dist_dir), html=True), name="recruiter_spa")

    @app.get("/health", response_model=HealthResponse)
    def health(request: Request) -> HealthResponse:
        rt = getattr(request.app.state, "vertical_slice", None)
        if rt is None:
            runtime_key = "vertical_slice_not_initialized"
        elif isinstance(rt.bundle.store, SQLiteStateStore):
            runtime_key = "vertical_slice_sqlite_sync"
        else:
            runtime_key = "vertical_slice_in_memory_sync"
        return HealthResponse(
            status="ok",
            runtime=runtime_key,
            sync=True,
            auth="none",
        )

    @app.post("/admin/reset", response_model=AdminResetResponse, tags=["admin"])
    def admin_reset(rt: VerticalSliceApiRuntime = Depends(get_runtime)) -> AdminResetResponse:
        try:
            result = rt.dev_reset_to_bootstrap_initial()
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return AdminResetResponse(
            store_revision=result.store_revision,
            pipeline_phase=result.pipeline_phase,
            sqlite_tables_cleared=result.sqlite_tables_cleared,
        )

    @app.get("/scoring-context", response_model=ScoringContextResponse)
    def get_scoring_context_route(
        rt: VerticalSliceApiRuntime = Depends(get_runtime),
    ) -> ScoringContextResponse:
        return _context_response(rt)

    @app.post("/scoring-context/organization", response_model=ScoringContextResponse)
    def post_organization_context(
        body: OrganizationContextBody,
        rt: VerticalSliceApiRuntime = Depends(get_runtime),
    ) -> ScoringContextResponse:
        try:
            author_organization_context_from_text(rt, body.raw_text, source_ref=body.source_ref)
        except RecruitmentUseCaseError as exc:
            raise_recruitment_http(exc, candidate_id=rt.candidate_id)
        return _context_response(rt)

    @app.post("/scoring-context/recruiter-actor", response_model=ScoringContextResponse)
    def post_recruiter_actor_context(
        body: RecruiterActorContextBody,
        rt: VerticalSliceApiRuntime = Depends(get_runtime),
    ) -> ScoringContextResponse:
        try:
            author_recruiter_actor_context_from_text(rt, body.raw_text, source_ref=body.source_ref)
        except RecruitmentUseCaseError as exc:
            raise_recruitment_http(exc, candidate_id=rt.candidate_id)
        return _context_response(rt)

    @app.post("/scoring-context/job/text", response_model=ScoringContextResponse)
    def post_job_context_text(
        body: JobContextTextBody,
        rt: VerticalSliceApiRuntime = Depends(get_runtime),
    ) -> ScoringContextResponse:
        try:
            author_job_context_from_text(rt, body.raw_text, source_ref=body.source_ref)
        except RecruitmentUseCaseError as exc:
            raise_recruitment_http(exc, candidate_id=rt.candidate_id)
        return _context_response(rt)

    @app.post("/scoring-context/job/pdf", response_model=ScoringContextResponse)
    def post_job_context_pdf(
        body: JobContextPdfBody,
        rt: VerticalSliceApiRuntime = Depends(get_runtime),
    ) -> ScoringContextResponse:
        try:
            author_job_context_from_pdf(rt, body.pdf_base64, file_name=body.file_name)
        except RecruitmentUseCaseError as exc:
            raise_recruitment_http(exc, candidate_id=rt.candidate_id)
        return _context_response(rt)

    @app.post("/scoring-context/job/recruiter-answers", response_model=ScoringContextResponse)
    def post_job_context_recruiter_answers(
        body: RecruiterJobAnswersBody,
        rt: VerticalSliceApiRuntime = Depends(get_runtime),
    ) -> ScoringContextResponse:
        try:
            author_job_context_from_recruiter_answers(
                rt,
                role_title=body.role_title,
                must_haves_answer=body.must_haves_answer,
                preferred_answer=body.preferred_answer,
                success_answer=body.success_answer,
                responsibilities_answer=body.responsibilities_answer,
            )
        except RecruitmentUseCaseError as exc:
            raise_recruitment_http(exc, candidate_id=rt.candidate_id)
        return _context_response(rt)

    @app.post("/scoring-context/refresh", response_model=ScoringContextResponse)
    def post_refresh_scoring_context(
        rt: VerticalSliceApiRuntime = Depends(get_runtime),
    ) -> ScoringContextResponse:
        try:
            refresh_active_scoring_context(rt)
        except RecruitmentUseCaseError as exc:
            raise_recruitment_http(exc, candidate_id=rt.candidate_id)
        return _context_response(rt)

    @app.post("/events", response_model=EventIngressResponse)
    def post_event(
        body: VerticalSliceIngressEventBody,
        rt: VerticalSliceApiRuntime = Depends(get_runtime),
    ) -> EventIngressResponse:
        cid = body.candidate_id if body.candidate_id is not None else VERTICAL_SLICE_DEFAULT_CANDIDATE_ID
        try:
            if policies.is_governance_event(body.event_type):
                result = record_recruiter_decision(
                    rt,
                    cid,
                    body.event_type,
                    body.payload,
                    correlation_id=body.correlation_id,
                )
            else:
                result = publish_recruitment_event(
                    rt,
                    cid,
                    body.event_type,
                    body.payload,
                    correlation_id=body.correlation_id,
                )
        except RecruitmentUseCaseError as exc:
            raise_recruitment_http(exc, candidate_id=cid)

        state_summary = None
        if result.state_summary is not None:
            state_summary = StateSummaryResponse(**result.state_summary)

        return EventIngressResponse(
            ingress_accepted=result.ingress_accepted,
            publish_status=result.publish_status,
            event_id=result.event_id,
            event_type=result.event_type,
            publish_result=result.publish_result,
            state_summary=state_summary,
        )

    @app.get("/state/{candidate_id}", response_model=StateSummaryResponse)
    def get_state(
        candidate_id: UUID,
        rt: VerticalSliceApiRuntime = Depends(get_runtime),
    ) -> StateSummaryResponse:
        try:
            summary = get_state_summary_for_candidate(rt, candidate_id)
        except RecruitmentUseCaseError as exc:
            raise_recruitment_http(exc, candidate_id=candidate_id)

        return StateSummaryResponse(**summary)

    @app.get("/timeline/{candidate_id}", response_model=TimelineResponse)
    def get_timeline_route(
        candidate_id: UUID,
        rt: VerticalSliceApiRuntime = Depends(get_runtime),
    ) -> TimelineResponse:
        try:
            tl = get_timeline_for_candidate(rt, candidate_id)
        except RecruitmentUseCaseError as exc:
            raise_recruitment_http(exc, candidate_id=candidate_id)

        return TimelineResponse(**tl)

    @app.get("/demo/candidate", response_model=DemoCandidateResponse)
    def get_demo_candidate_route(rt: VerticalSliceApiRuntime = Depends(get_runtime)) -> DemoCandidateResponse:
        body = get_demo_candidate(rt)
        state_summary = body.get("state_summary")
        return DemoCandidateResponse(
            candidate_id=body["candidate_id"],
            profile=body["profile"],
            pipeline_phase=body["pipeline_phase"],
            state_summary=StateSummaryResponse(**state_summary) if state_summary else None,
            skill_summaries=body["skill_summaries"],
            inactive_reason=body.get("inactive_reason"),
        )

    @app.get("/candidates", response_model=List[CandidateListItem])
    def list_candidates_route(
        rt: VerticalSliceApiRuntime = Depends(get_runtime),
    ) -> List[CandidateListItem]:
        rows = list_candidates(rt)
        return [CandidateListItem(**row) for row in rows]

    @app.post("/candidates/{candidate_id}/action", response_model=CandidateViewResponse)
    def post_candidate_action(
        candidate_id: UUID,
        body: CandidateActionBody,
        rt: VerticalSliceApiRuntime = Depends(get_runtime),
    ) -> CandidateViewResponse:
        try:
            view = perform_candidate_action(
                rt,
                candidate_id,
                body.event_type,
                body.payload or None,
            )
        except RecruitmentUseCaseError as exc:
            raise_recruitment_http(exc, candidate_id=candidate_id)
        return CandidateViewResponse(candidate_id=str(candidate_id), **view)

    @app.post("/candidates/{candidate_id}/cv/pdf", response_model=EventIngressResponse)
    def post_candidate_pdf_cv(
        candidate_id: UUID,
        body: CandidatePdfIngressBody,
        rt: VerticalSliceApiRuntime = Depends(get_runtime),
    ) -> EventIngressResponse:
        try:
            result = submit_cv_pdf(
                rt,
                candidate_id,
                body.pdf_base64,
                file_name=body.file_name,
                correlation_id=body.correlation_id,
            )
        except RecruitmentUseCaseError as exc:
            raise_recruitment_http(exc, candidate_id=candidate_id)

        state_summary = None
        if result.state_summary is not None:
            state_summary = StateSummaryResponse(**result.state_summary)

        return EventIngressResponse(
            ingress_accepted=result.ingress_accepted,
            publish_status=result.publish_status,
            event_id=result.event_id,
            event_type=result.event_type,
            publish_result=result.publish_result,
            state_summary=state_summary,
        )

    @app.get("/candidate/{candidate_id}", response_model=CandidateViewResponse)
    def get_candidate_view_route(
        candidate_id: UUID,
        rt: VerticalSliceApiRuntime = Depends(get_runtime),
    ) -> CandidateViewResponse:
        try:
            view = get_candidate_view_for_runtime(rt, candidate_id)
        except RecruitmentUseCaseError as exc:
            raise_recruitment_http(exc, candidate_id=candidate_id)
        return CandidateViewResponse(candidate_id=str(candidate_id), **view)

    @app.post("/demo/run", response_model=DemoRunResponse)
    def post_demo_run(rt: VerticalSliceApiRuntime = Depends(get_runtime)) -> DemoRunResponse:
        try:
            snap = run_primary_demo_sequence(rt, rt.candidate_id)
        except RecruitmentUseCaseError as exc:
            raise_recruitment_http(exc, candidate_id=rt.candidate_id)
        got = rt.bundle.store.get(rt.bundle.state_id)
        if not got.ok or got.meta is None:
            raise HTTPException(status_code=500, detail="state store meta missing after demo run")
        return DemoRunResponse(
            message="primary vertical slice sequence published via bus",
            state_summary=StateSummaryResponse(
                **get_state_summary(snap, store_revision=got.meta.store_revision)
            ),
        )

    @app.get("/demo", response_class=HTMLResponse)
    def get_demo_page(rt: VerticalSliceApiRuntime = Depends(get_runtime)) -> HTMLResponse:
        return HTMLResponse(content=build_demo_recruiter_html(rt))

    return app


app = create_app()
