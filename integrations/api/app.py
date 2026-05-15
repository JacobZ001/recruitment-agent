"""
Thin FastAPI boundary for the recruiter vertical slice.

HTTP concerns only; recruitment business actions live in ``modules.recruitment``.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse

from integrations.api.demo_page import build_demo_recruiter_html
from integrations.api.schemas_http import (
    AdminResetResponse,
    CandidateViewResponse,
    DemoCandidateResponse,
    DemoRunResponse,
    EventIngressResponse,
    HealthResponse,
    StateSummaryResponse,
    TimelineResponse,
    VerticalSliceIngressEventBody,
)
from integrations.api.session import VerticalSliceApiRuntime
from modules.recruitment import (
    CandidateNotFoundError,
    DemoRunPreconditionError,
    get_candidate_view_for_runtime,
    get_demo_candidate,
    get_state_summary,
    get_timeline,
    policies,
    record_recruiter_decision,
    run_primary_demo_sequence,
    submit_cv,
)
from runtime.bootstrap_vertical_slice import VERTICAL_SLICE_DEFAULT_CANDIDATE_ID
from runtime.persistence.sqlite_state_store import SQLiteStateStore


def get_runtime(request: Request) -> VerticalSliceApiRuntime:
    rt = getattr(request.app.state, "vertical_slice", None)
    if rt is None:
        raise HTTPException(status_code=503, detail="runtime not initialized")
    return rt


def _candidate_not_found_http(candidate_id: UUID, *, message: str) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={
            "code": "candidate_not_found",
            "message": message,
            "candidate_id": str(candidate_id),
        },
    )


DEFAULT_VERTICAL_SLICE_DB_PATH = "data/app.db"


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
    @asynccontextmanager
    async def lifespan(app: FastAPI):
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
                result = submit_cv(
                    rt,
                    cid,
                    body.event_type,
                    body.payload,
                    correlation_id=body.correlation_id,
                )
        except CandidateNotFoundError:
            raise _candidate_not_found_http(
                cid,
                message="candidate_id does not match this single-aggregate runtime",
            ) from None

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
            policies.validate_single_tenant_candidate(rt, candidate_id)
        except CandidateNotFoundError:
            raise HTTPException(status_code=404, detail="candidate_id not found for this runtime") from None

        got = rt.bundle.store.get_for_candidate(candidate_id)
        if not got.ok or got.snapshot is None or got.meta is None:
            raise HTTPException(status_code=404, detail="no orchestration state for candidate")

        return StateSummaryResponse(**get_state_summary(got.snapshot, store_revision=got.meta.store_revision))

    @app.get("/timeline/{candidate_id}", response_model=TimelineResponse)
    def get_timeline_route(
        candidate_id: UUID,
        rt: VerticalSliceApiRuntime = Depends(get_runtime),
    ) -> TimelineResponse:
        try:
            policies.validate_single_tenant_candidate(rt, candidate_id)
        except CandidateNotFoundError:
            raise HTTPException(status_code=404, detail="candidate_id not found for this runtime") from None

        tl = get_timeline(rt)
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

    @app.get("/candidate/{candidate_id}", response_model=CandidateViewResponse)
    def get_candidate_view_route(
        candidate_id: UUID,
        rt: VerticalSliceApiRuntime = Depends(get_runtime),
    ) -> CandidateViewResponse:
        try:
            view = get_candidate_view_for_runtime(rt, candidate_id)
        except CandidateNotFoundError as exc:
            msg = str(exc)
            if "no orchestration state" in msg:
                raise HTTPException(status_code=404, detail="no orchestration state for candidate") from exc
            raise HTTPException(status_code=404, detail="candidate_id not found for this runtime") from exc
        return CandidateViewResponse(candidate_id=str(candidate_id), **view)

    @app.post("/demo/run", response_model=DemoRunResponse)
    def post_demo_run(rt: VerticalSliceApiRuntime = Depends(get_runtime)) -> DemoRunResponse:
        try:
            snap = run_primary_demo_sequence(rt, rt.candidate_id)
        except DemoRunPreconditionError as e:
            raise HTTPException(status_code=409, detail=str(e)) from e
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
