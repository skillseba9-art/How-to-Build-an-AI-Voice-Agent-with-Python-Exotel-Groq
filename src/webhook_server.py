"""
Webhook Server — FastAPI server that n8n calls for CRM operations.

Endpoints:
  GET  /health                     → server status check
  GET  /leads/fetch?limit=20       → fetch eligible leads from Sheets
  POST /leads/create               → append new lead row
  POST /leads/update               → update existing lead by phone
  POST /leads/schedule-followup    → post-call follow-up update

Run:
  cd Student_Supervise
  venv\\Scripts\\python src/webhook_server.py

Server starts on http://localhost:8000
n8n workflows call: http://host.docker.internal:8000  (if n8n in Docker)
                or: http://<your-local-ip>:8000       (if n8n on same network)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

# Windows console UTF-8 fix
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from typing import Optional
import uvicorn

from crm_updater import (
    push_to_crm,
    update_lead_in_crm,
    fetch_eligible_leads,
    schedule_followup,
)

app = FastAPI(
    title="Modern Academy CRM Webhook Server",
    description="Internal API for n8n ↔ Google Sheets CRM integration",
    version="1.0.0",
)


# ─── Request models ───────────────────────────────────────────────────────────

class CreateLeadRequest(BaseModel):
    phone: str
    call_outcome: str
    ai_summary: str
    language: str = "Hindi"
    student_name: Optional[str] = None
    parent_name: Optional[str]  = None
    class_interested: Optional[str] = None
    interest_level: Optional[str]   = None
    call_duration: str = ""
    transcript_link: str = ""
    recording_link: str  = ""
    inbound_outbound: str = "Outbound"


class UpdateLeadRequest(BaseModel):
    phone: str
    updates: dict  # keys must match COL dict in crm_updater


class ScheduleFollowupRequest(BaseModel):
    phone: str
    outcome: str
    new_followup_date: str = ""  # optional override, format: YYYY-MM-DD


# ─── Routes ──────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "Modern Academy CRM Webhook Server",
        "version": "1.0.0",
    }


@app.get("/exotel/voice", response_class=PlainTextResponse)
@app.post("/exotel/voice", response_class=PlainTextResponse)
def exotel_voice():
    """
    Minimal TwiML endpoint for Exotel/voice testing.
    Exotel will call this URL when a call is initiated.
    """
    xml = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<Response>
  <Say language=\"hi-IN\">Namaste! This is Modern Academy AI admission test call.</Say>
  <Play>https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3</Play>
</Response>"""
    return PlainTextResponse(content=xml, media_type="application/xml")


@app.get("/leads/fetch")
def get_eligible_leads(limit: int = Query(default=20, ge=1, le=100)):
    """
    Return leads from Google Sheets that are eligible for follow-up.
    n8n Lead Fetcher workflow calls this endpoint on schedule.
    """
    try:
        leads = fetch_eligible_leads(limit=limit)
        return {
            "success": True,
            "count": len(leads),
            "leads": leads,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/leads/create")
def create_lead(req: CreateLeadRequest):
    """
    Append a new lead row to Google Sheets.
    Called by n8n after a voice call completes.
    """
    success = push_to_crm(
        phone=req.phone,
        call_outcome=req.call_outcome,
        ai_summary=req.ai_summary,
        language=req.language,
        student_name=req.student_name,
        parent_name=req.parent_name,
        class_interested=req.class_interested,
        interest_level=req.interest_level,
        call_duration=req.call_duration,
        transcript_link=req.transcript_link,
        recording_link=req.recording_link,
        inbound_outbound=req.inbound_outbound,
    )
    if not success:
        raise HTTPException(status_code=500, detail="CRM push failed")
    return {"success": True, "message": f"Lead created for {req.phone}"}


@app.post("/leads/update")
def update_lead(req: UpdateLeadRequest):
    """
    Update specific columns of an existing lead row.
    Called by n8n when CRM data needs patching.
    """
    found = update_lead_in_crm(req.phone, req.updates)
    if not found:
        raise HTTPException(
            status_code=404,
            detail=f"Lead not found for phone={req.phone}. Use /leads/create to add new lead."
        )
    return {"success": True, "message": f"Lead updated for {req.phone}"}


@app.post("/leads/schedule-followup")
def schedule_followup_route(req: ScheduleFollowupRequest):
    """
    Post-call update: set next follow-up date and update call outcome.
    Called by n8n Follow-up Scheduler workflow.
    """
    success = schedule_followup(
        phone=req.phone,
        outcome=req.outcome,
        new_followup_date=req.new_followup_date,
    )
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Lead not found for phone={req.phone}"
        )
    return {
        "success": True,
        "message": f"Follow-up scheduled for {req.phone} (outcome: {req.outcome})",
    }


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 55)
    print("  Modern Academy CRM Webhook Server")
    print("  http://localhost:8000")
    print("  Docs: http://localhost:8000/docs")
    print("=" * 55)
    uvicorn.run("webhook_server:app", host="0.0.0.0", port=8000, reload=False)
