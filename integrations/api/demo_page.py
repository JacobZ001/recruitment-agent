"""Minimal HTML for the recruiter vertical-slice demo (no assets, no SPA)."""

from __future__ import annotations

import html
import json
from typing import Any, Dict

from runtime.bootstrap_vertical_slice import vertical_slice_timeline_text
from runtime.demo_candidate_fixture import DEMO_CANDIDATE_DISPLAY

from integrations.api.demo_summary import vertical_slice_demo_skill_summaries
from integrations.api.session import VerticalSliceApiRuntime


def build_demo_recruiter_html(rt: VerticalSliceApiRuntime) -> str:
    profile = DEMO_CANDIDATE_DISPLAY
    summaries = vertical_slice_demo_skill_summaries(rt.bundle)
    timeline = vertical_slice_timeline_text(rt.bundle)
    cid = str(rt.candidate_id)

    got = rt.bundle.store.get(rt.bundle.state_id)
    phase = ""
    if got.ok and got.snapshot is not None:
        phase = got.snapshot.pipeline.phase.value

    def esc(x: Any) -> str:
        return html.escape(str(x), quote=True)

    gov_payload_approve: Dict[str, Any] = {
        "actor_id": "demo-recruiter",
        "actor_type": "recruiter",
        "reason": "Demo recruiter approval (deterministic governance ingress).",
        "evidence_refs": list(profile.get("evidence_refs") or ()),
    }
    gov_payload_reject = {
        **gov_payload_approve,
        "reason": "Demo recruiter rejection (deterministic governance ingress).",
    }
    gov_post = {
        **gov_payload_approve,
        "reason": "Demo post-evaluation recruiter action (deterministic governance ingress).",
    }

    skills_block = esc(json.dumps(summaries, indent=2, sort_keys=True))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Vertical slice demo — thin recruiter surface</title>
</head>
<body>
  <h1>BlueOcean vertical slice (demo only)</h1>
  <p>Deterministic in-memory slice: not a production UI. Governance actions call <code>POST /events</code>.</p>

  <h2>Candidate profile (fixture)</h2>
  <ul>
    <li><strong>Name</strong>: {esc(profile.get("candidate_name"))}</li>
    <li><strong>Target role</strong>: {esc(profile.get("target_role"))}</li>
    <li><strong>Experience</strong>: {esc(profile.get("years_experience"))} years</li>
    <li><strong>Location</strong>: {esc(profile.get("location"))}</li>
    <li><strong>Work authorization</strong>: {esc(profile.get("work_authorization"))}</li>
    <li><strong>Education</strong>: {esc(profile.get("education"))}</li>
    <li><strong>Skills</strong>: {esc(", ".join(profile.get("skills") or []))}</li>
    <li><strong>Summary</strong>: {esc(profile.get("summary"))}</li>
    <li><strong>Evidence refs</strong>: {esc(", ".join(profile.get("evidence_refs") or []))}</li>
  </ul>

  <h2>Pipeline</h2>
  <p><strong>Current phase</strong>: {esc(phase)}</p>
  <p><strong>Default candidate id</strong>: <code>{esc(cid)}</code></p>

  <h2>Score / filter summaries (from last skill runs)</h2>
  <pre>{skills_block}</pre>

  <h2>Workflow timeline</h2>
  <pre>{esc(timeline)}</pre>

  <h2>Governance (via event bus)</h2>
  <p>These buttons POST JSON to <code>/events</code> with typed governance payloads (no direct state mutation).</p>
  <p>After <code>deep_scored</code>: approve → <code>shortlisted</code>, then schedule interview → complete → send offer → mark hired (each step only valid in the matching phase; wrong phase = deterministic NOOP).</p>
  <p>Typical sequence: <code>POST /demo/run</code> (or stepped <code>POST /events</code>), then use the buttons below in order.</p>
  <button type="button" id="btn-run">POST /demo/run</button>
  <button type="button" id="btn-approve">recruiter_approve_candidate</button>
  <button type="button" id="btn-schedule">recruiter_schedule_interview</button>
  <button type="button" id="btn-complete">recruiter_complete_interview</button>
  <button type="button" id="btn-offer">recruiter_send_offer</button>
  <button type="button" id="btn-hired">recruiter_mark_hired</button>
  <button type="button" id="btn-reject">recruiter_reject_candidate</button>
  <p id="status"></p>

  <h3>curl examples</h3>
  <pre>curl -s -X POST http://127.0.0.1:8000/demo/run
curl -s http://127.0.0.1:8000/demo/candidate
curl -s -X POST http://127.0.0.1:8000/events -H "Content-Type: application/json" \\
  -d @approve.json</pre>
  <p>Where <code>approve.json</code> contains <code>event_type</code>, optional <code>candidate_id</code>, and a governance <code>payload</code> matching the approve button body.</p>

  <script>
    const candidateId = {json.dumps(cid)};
    const govApprove = {json.dumps(gov_payload_approve)};
    const govReject = {json.dumps(gov_payload_reject)};
    const govPost = {json.dumps(gov_post)};
    async function postEvent(eventType, payload) {{
      const r = await fetch('/events', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ event_type: eventType, candidate_id: candidateId, payload }}),
      }});
      const t = await r.text();
      document.getElementById('status').textContent = r.status + ' ' + t.slice(0, 500);
      location.reload();
    }}
    document.getElementById('btn-run').onclick = async () => {{
      const r = await fetch('/demo/run', {{ method: 'POST' }});
      const t = await r.text();
      document.getElementById('status').textContent = r.status + ' ' + t.slice(0, 500);
      location.reload();
    }};
    document.getElementById('btn-approve').onclick = () => postEvent('recruiter_approve_candidate', govApprove);
    document.getElementById('btn-schedule').onclick = () => postEvent('recruiter_schedule_interview', govPost);
    document.getElementById('btn-complete').onclick = () => postEvent('recruiter_complete_interview', govPost);
    document.getElementById('btn-offer').onclick = () => postEvent('recruiter_send_offer', govPost);
    document.getElementById('btn-hired').onclick = () => postEvent('recruiter_mark_hired', govPost);
    document.getElementById('btn-reject').onclick = () => postEvent('recruiter_reject_candidate', govReject);
  </script>
</body>
</html>
"""
