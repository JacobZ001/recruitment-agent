"""
Thin FastAPI boundary for the recruiter vertical slice.

Ingress only: ``POST /events`` publishes validated :class:`~interfaces.event_bus_interface.EventEnvelope`
records onto the in-memory bus; orchestration remains unchanged (subscriber → orchestrator → store).
No workflow policy or direct state mutation here.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Optional
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Request

from integrations.api.schemas_http import (
    EventIngressResponse,
    HealthResponse,
    StateSummaryResponse,
    TimelineResponse,
    VerticalSliceIngressEventBody,
)
from integrations.api.session import VerticalSliceApiRuntime
from interfaces.event_bus_interface import DeliveryStatus
from runtime.bootstrap_vertical_slice import (
    VERTICAL_SLICE_DEFAULT_CANDIDATE_ID,
    vertical_slice_timeline_text,
    _envelope,
    _FIXED_CLOCK,
)
from schemas.state_schema import OrchestrationState


def _state_summary_from_snapshot(
    snap: OrchestrationState,
    *,
    store_revision: Optional[int],
) -> StateSummaryResponse:
    return StateSummaryResponse(
        pipeline_phase=snap.pipeline.phase.value,
        transitions_count=len(snap.transitions),
        state_id=str(snap.id),
        store_revision=store_revision,
    )


def _publish_payload_merge(base_payload: Dict[str, Any], extra: Dict[str, Any], seq: int) -> Dict[str, Any]:
    out = dict(base_payload)
    out.update(extra)
    out["api_sequence"] = seq
    return out


def _timeline_catalog_note(rt: VerticalSliceApiRuntime) -> Optional[str]:
    bus = rt.bundle.bus
    rec = getattr(bus, "recorded_envelopes", None)
    if rec is None:
        return (
            "This bus implementation does not expose recorded_envelopes; merged catalog "
            "cannot include runtime-emitted publishes—ingress labels for nested orchestration "
            "runs may show as unknown types unless an explicit catalog is supplied elsewhere."
        )
    if len(rec) == 0:
        return "No envelopes recorded yet; publish events before expecting a rich timeline."
    return None


def get_runtime(request: Request) -> VerticalSliceApiRuntime:
    rt = getattr(request.app.state, "vertical_slice", None)
    if rt is None:
        raise HTTPException(status_code=503, detail="runtime not initialized")
    return rt


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.vertical_slice = VerticalSliceApiRuntime()
        yield

    app = FastAPI(
        title="BlueOcean vertical slice (reference)",
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            runtime="vertical_slice_in_memory_sync",
            sync=True,
            auth="none",
        )

    @app.post("/events", response_model=EventIngressResponse)
    def post_event(
        body: VerticalSliceIngressEventBody,
        rt: VerticalSliceApiRuntime = Depends(get_runtime),
    ) -> EventIngressResponse:
        cid = body.candidate_id if body.candidate_id is not None else VERTICAL_SLICE_DEFAULT_CANDIDATE_ID
        if cid != rt.candidate_id:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "candidate_not_found",
                    "message": "candidate_id does not match this single-aggregate runtime",
                    "candidate_id": str(cid),
                },
            )

        seq = rt.next_publish_sequence()
        correlation = body.correlation_id if body.correlation_id is not None else cid

        env = _envelope(
            event_type=body.event_type,
            candidate_id=cid,
            correlation_id=correlation,
            occurred_at=_FIXED_CLOCK,
            seq=seq,
        )
        merged_payload = _publish_payload_merge(dict(env.payload), body.payload, seq)
        env = env.model_copy(update={"payload": merged_payload})

        pr = rt.bundle.bus.publish(env)
        accepted = pr.status == DeliveryStatus.ACCEPTED
        pub_dump = pr.model_dump(mode="json")

        state_summary: Optional[StateSummaryResponse] = None
        cur = rt.bundle.store.get(rt.bundle.state_id)
        if cur.ok and cur.snapshot is not None and cur.meta is not None:
            state_summary = _state_summary_from_snapshot(
                cur.snapshot,
                store_revision=cur.meta.store_revision,
            )

        return EventIngressResponse(
            ingress_accepted=accepted,
            publish_status=pr.status.value,
            event_id=str(env.event_id),
            event_type=env.event_type,
            publish_result=pub_dump,
            state_summary=state_summary,
        )

    @app.get("/state/{candidate_id}", response_model=StateSummaryResponse)
    def get_state(
        candidate_id: UUID,
        rt: VerticalSliceApiRuntime = Depends(get_runtime),
    ) -> StateSummaryResponse:
        if candidate_id != rt.candidate_id:
            raise HTTPException(status_code=404, detail="candidate_id not found for this runtime")

        got = rt.bundle.store.get_for_candidate(candidate_id)
        if not got.ok or got.snapshot is None or got.meta is None:
            raise HTTPException(status_code=404, detail="no orchestration state for candidate")

        return _state_summary_from_snapshot(got.snapshot, store_revision=got.meta.store_revision)

    @app.get("/timeline/{candidate_id}", response_model=TimelineResponse)
    def get_timeline(
        candidate_id: UUID,
        rt: VerticalSliceApiRuntime = Depends(get_runtime),
    ) -> TimelineResponse:
        if candidate_id != rt.candidate_id:
            raise HTTPException(status_code=404, detail="candidate_id not found for this runtime")

        note = _timeline_catalog_note(rt)
        text = vertical_slice_timeline_text(rt.bundle)
        return TimelineResponse(timeline_text=text, catalog_note=note)

    return app


app = create_app()
