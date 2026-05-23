"""
Human-readable vertical-slice timeline text (delegates to ``runtime.inspection``).
"""

from __future__ import annotations

from typing import Any, Optional, Sequence

from interfaces.event_bus_interface import EventEnvelope

from .catalog import resolve_vertical_slice_inspection_catalog


def vertical_slice_timeline_text(
    bundle: Any,
    envelope_catalog: Optional[Sequence[EventEnvelope]] = None,
    *,
    include_operator_navigation: bool = True,
) -> str:
    """Human-readable multi-run timeline (see ``runtime.inspection`` renderers)."""
    from runtime.inspection import merge_catalog_streams, render_vertical_slice_timeline_text

    fin = bundle.store.get(bundle.state_id)
    if envelope_catalog is None:
        merged = resolve_vertical_slice_inspection_catalog(bundle)
    else:
        merged = merge_catalog_streams(envelope_catalog)
    return render_vertical_slice_timeline_text(
        run_history=bundle.subscriber.run_history,
        envelope_catalog=merged,
        final_state=fin.snapshot if fin.ok else None,
        include_operator_navigation=include_operator_navigation,
    )
