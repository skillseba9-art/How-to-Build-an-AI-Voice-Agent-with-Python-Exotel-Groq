"""
CRM Updater — reads and writes Google Sheets (Lead Management tab).

Google Sheet columns — 28 total (job description spec):
 1  Lead ID
 2  Student Name
 3  Parent Name
 4  Phone Number
 5  Class Interested
 6  Lead Source
 7  Lead Status
 8  Interest Level
 9  Call Status
10  Call Outcome
11  Preferred Language
12  Last Call Date
13  Last Call Time
14  Next Follow-up Date
15  Follow-up Count
16  Interested In Visit
17  WhatsApp Sent
18  Brochure Sent
19  Counselor Needed
20  Assigned Counselor
21  Admission Probability
22  AI Summary
23  Transcript Link
24  Recording Link
25  Call Duration
26  Inbound/Outbound
27  Converted
28  Admission Completed

Strategy: gspread (direct) first, n8n webhook as fallback.
"""

import os
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "")
SHEET_ID        = os.getenv("GOOGLE_SHEET_ID", "1BpnN88jQHOY5gLi1JcVopVFg6pOWfOR2jwn6flX2pdA")
SA_JSON_PATH    = ROOT / os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "credentials/google_service_account.json")
SHEET_TAB       = "Lead Management"

# ─── Column index map (0-based) ──────────────────────────────────────────────
COL = {
    "lead_id":             0,
    "student_name":        1,
    "parent_name":         2,
    "phone":               3,
    "class_interested":    4,
    "lead_source":         5,
    "lead_status":         6,
    "interest_level":      7,
    "call_status":         8,
    "call_outcome":        9,
    "language":            10,
    "last_call_date":      11,
    "last_call_time":      12,
    "next_followup":       13,
    "followup_count":      14,
    "interested_visit":    15,
    "whatsapp_sent":       16,
    "brochure_sent":       17,
    "counselor_needed":    18,
    "assigned_counselor":  19,
    "admission_prob":      20,
    "ai_summary":          21,
    "transcript_link":     22,
    "recording_link":      23,
    "call_duration":       24,
    "inbound_outbound":    25,
    "converted":           26,
    "admission_completed": 27,
}

# ─── Outcome mapping tables ───────────────────────────────────────────────────
_STATUS_MAP = {
    "interested":        "Interested",
    "highly_interested": "Highly Interested",
    "busy":              "Busy/Call Later",
    "not_interested":    "Not Interested",
    "no_answer":         "No Answer",
    "visit_scheduled":   "Callback Scheduled",
    "wants_human":       "Human Escalated",
    "wrong_number":      "Invalid",
    "already_admitted":  "Admission Completed",
}

_INTEREST_MAP = {
    "interested":        "Medium",
    "highly_interested": "High",
    "busy":              "Medium",
    "not_interested":    "Low",
    "no_answer":         "None",
    "visit_scheduled":   "High",
    "wants_human":       "High",
    "wrong_number":      "None",
    "already_admitted":  "High",
}

_PROB_MAP = {
    "interested":        "50%",
    "highly_interested": "80%",
    "busy":              "40%",
    "not_interested":    "0%",
    "no_answer":         "20%",
    "visit_scheduled":   "80%",
    "wants_human":       "60%",
    "wrong_number":      "0%",
    "already_admitted":  "100%",
}

_CALL_STATUS_MAP = {
    "interested":        "Connected",
    "highly_interested": "Connected",
    "busy":              "Connected",
    "not_interested":    "Connected",
    "no_answer":         "No Answer",
    "visit_scheduled":   "Connected",
    "wants_human":       "Connected",
    "wrong_number":      "Wrong Number",
    "already_admitted":  "Connected",
}

_FOLLOWUP_DAYS: dict[str, int] = {
    "interested":        2,
    "highly_interested": 0,
    "busy":              0,   # 4 hours — handled specially
    "no_answer":         1,
    "not_interested":    15,
    "visit_scheduled":   1,
    "wants_human":       0,
    "wrong_number":      999,
    "already_admitted":  999,
}

_NEEDS_COUNSELOR = {"highly_interested", "wants_human", "visit_scheduled"}

# Statuses that should NOT be fetched for follow-up
CLOSED_STATUSES = {"Not Interested", "Invalid", "Admission Completed"}


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _next_followup(outcome: str) -> str:
    now = datetime.now()
    if outcome == "busy":
        return (now + timedelta(hours=4)).strftime("%Y-%m-%d %H:%M")
    days = _FOLLOWUP_DAYS.get(outcome, 2)
    if days >= 999:
        return ""
    if days == 0:
        return now.strftime("%Y-%m-%d")
    return (now + timedelta(days=days)).strftime("%Y-%m-%d")


def _make_lead_id() -> str:
    return f"MA-LEAD-{random.randint(1000, 9999)}"


def _col_letter(n: int) -> str:
    """Convert 1-based column number to Excel letter (A, B, ..., AA, AB ...)."""
    result = ""
    while n:
        n, rem = divmod(n - 1, 26)
        result = chr(65 + rem) + result
    return result


def _get_gspread_ws():
    """Return (ws, orig_send, requests_module) with Windows SSL bypass."""
    import ssl, urllib3, requests as _req
    urllib3.disable_warnings()
    os.environ["REQUESTS_CA_BUNDLE"] = ""
    os.environ["CURL_CA_BUNDLE"]     = ""
    ssl._create_default_https_context = ssl._create_unverified_context  # noqa

    _orig_send = _req.Session.send
    def _send_no_verify(self, request, **kwargs):
        kwargs["verify"] = False
        return _orig_send(self, request, **kwargs)
    _req.Session.send = _send_no_verify

    import gspread
    from google.oauth2.service_account import Credentials
    from google.auth.transport.requests import AuthorizedSession

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds  = Credentials.from_service_account_file(str(SA_JSON_PATH), scopes=scopes)
    authed = AuthorizedSession(creds)
    gc     = gspread.Client(auth=creds, session=authed)
    sh     = gc.open_by_key(SHEET_ID)
    ws     = sh.worksheet(SHEET_TAB)
    return ws, _orig_send, _req


# ─── APPEND: create new lead row ─────────────────────────────────────────────

def _push_gspread(row_data: list) -> bool:
    try:
        ws, orig, _req = _get_gspread_ws()
        ws.append_row(row_data, value_input_option="USER_ENTERED")
        _req.Session.send = orig
        return True
    except Exception as exc:
        print(f"  gspread error: {exc}")
        return False


def _push_n8n(payload: dict) -> bool:
    if not N8N_WEBHOOK_URL:
        return False
    try:
        import ssl, urllib3
        urllib3.disable_warnings()
        resp = requests.post(N8N_WEBHOOK_URL, json=payload, timeout=10, verify=False)
        resp.raise_for_status()
        return True
    except Exception as exc:
        print(f"  n8n webhook error: {exc}")
        return False


def push_to_crm(
    phone: str,
    call_outcome: str,
    ai_summary: str,
    language: str = "Hindi",
    student_name: Optional[str] = None,
    parent_name: Optional[str]  = None,
    class_interested: Optional[str] = None,
    interest_level: Optional[str]   = None,
    call_duration: str = "",
    transcript_link: str = "",
    recording_link: str = "",
    inbound_outbound: str = "Outbound",
) -> bool:
    """
    Append a NEW lead row to Lead Management (28 columns).
    Tries gspread direct first, falls back to n8n webhook.
    """
    now = datetime.now()

    lead_status      = _STATUS_MAP.get(call_outcome, "New Lead")
    int_level        = interest_level or _INTEREST_MAP.get(call_outcome, "None")
    admit_prob       = _PROB_MAP.get(call_outcome, "20%")
    call_status      = _CALL_STATUS_MAP.get(call_outcome, "Connected")
    next_fup         = _next_followup(call_outcome)
    interested_visit = "Yes" if call_outcome in ("highly_interested", "visit_scheduled") else "Pending"
    counselor_needed = "Yes" if call_outcome in _NEEDS_COUNSELOR else "No"
    converted        = "Yes" if call_outcome in ("highly_interested", "visit_scheduled") else "No"
    admission_done   = "Yes" if call_outcome == "already_admitted" else "No"

    row = [""] * 28
    row[COL["lead_id"]]             = _make_lead_id()
    row[COL["student_name"]]        = student_name or ""
    row[COL["parent_name"]]         = parent_name  or ""
    row[COL["phone"]]               = phone
    row[COL["class_interested"]]    = class_interested or ""
    row[COL["lead_source"]]         = "AI Voice Call"
    row[COL["lead_status"]]         = lead_status
    row[COL["interest_level"]]      = int_level
    row[COL["call_status"]]         = call_status
    row[COL["call_outcome"]]        = call_outcome
    row[COL["language"]]            = language
    row[COL["last_call_date"]]      = now.strftime("%Y-%m-%d")
    row[COL["last_call_time"]]      = now.strftime("%H:%M:%S")
    row[COL["next_followup"]]       = next_fup
    row[COL["followup_count"]]      = 1
    row[COL["interested_visit"]]    = interested_visit
    row[COL["whatsapp_sent"]]       = "No"
    row[COL["brochure_sent"]]       = "No"
    row[COL["counselor_needed"]]    = counselor_needed
    row[COL["assigned_counselor"]]  = ""
    row[COL["admission_prob"]]      = admit_prob
    row[COL["ai_summary"]]          = ai_summary[:500]
    row[COL["transcript_link"]]     = transcript_link
    row[COL["recording_link"]]      = recording_link
    row[COL["call_duration"]]       = call_duration
    row[COL["inbound_outbound"]]    = inbound_outbound
    row[COL["converted"]]           = converted
    row[COL["admission_completed"]] = admission_done

    print(f"Pushing to CRM (phone={phone}, outcome={call_outcome})...")
    if SA_JSON_PATH.exists():
        if _push_gspread(row):
            print(f"  CRM updated via Google Sheets (outcome: {call_outcome})")
            return True

    payload = {k: row[v] for k, v in COL.items()}
    payload["phone"] = phone
    if _push_n8n(payload):
        print(f"  CRM updated via n8n webhook (outcome: {call_outcome})")
        return True

    print("  CRM push FAILED — both gspread and n8n unavailable")
    return False


# ─── UPDATE: patch specific columns in existing row ──────────────────────────

def update_lead_in_crm(phone: str, updates: dict) -> bool:
    """
    Find the row with matching phone number and update given columns.
    `updates` keys must match COL dict (e.g. "lead_status", "followup_count").
    Returns True on success, False if lead not found (caller should push_to_crm).
    """
    if not SA_JSON_PATH.exists():
        print("  Service account JSON not found — cannot update CRM")
        return False
    try:
        ws, orig, _req = _get_gspread_ws()
        all_values = ws.get_all_values()

        # Find row by phone (column D = index 3)
        row_idx = None
        for i, row in enumerate(all_values[1:], start=2):
            if len(row) > COL["phone"] and row[COL["phone"]] == phone:
                row_idx = i
                break

        if row_idx is None:
            print(f"  Lead not found for phone={phone}")
            _req.Session.send = orig
            return False

        # Build batch update cells
        batch = []
        for key, value in updates.items():
            col_idx = COL.get(key)
            if col_idx is None:
                print(f"  Unknown column: {key}, skipping")
                continue
            cell = f"{_col_letter(col_idx + 1)}{row_idx}"
            batch.append({"range": cell, "values": [[str(value)]]})

        if batch:
            ws.batch_update(batch, value_input_option="USER_ENTERED")
            print(f"  Updated {len(batch)} columns for phone={phone} at row {row_idx}")

        _req.Session.send = orig
        return True
    except Exception as exc:
        print(f"  update_lead_in_crm error: {exc}")
        return False


# ─── FETCH: eligible leads for follow-up calling ─────────────────────────────

def fetch_eligible_leads(limit: int = 20) -> list[dict]:
    """
    Read Lead Management sheet and return leads eligible for follow-up call.

    Eligible criteria:
      - Phone not empty
      - Lead Status NOT in CLOSED_STATUSES
      - Follow-up Count < 5
      - Next Follow-up Date <= today  (or empty = immediate)
    """
    if not SA_JSON_PATH.exists():
        print("  Service account JSON not found")
        return []
    try:
        ws, orig, _req = _get_gspread_ws()
        all_values = ws.get_all_values()
        _req.Session.send = orig

        if len(all_values) < 2:
            return []

        today    = datetime.now().date()
        eligible = []

        for row in all_values[1:]:
            row = row + [""] * (28 - len(row))   # pad to 28

            phone          = row[COL["phone"]].strip()
            lead_status    = row[COL["lead_status"]].strip()
            followup_count = int(row[COL["followup_count"]] or 0)
            next_fup_str   = row[COL["next_followup"]].strip()

            if not phone:
                continue
            if lead_status in CLOSED_STATUSES:
                continue
            if followup_count >= 5:
                continue

            due = True
            if next_fup_str:
                try:
                    fup_date = datetime.strptime(next_fup_str[:10], "%Y-%m-%d").date()
                    due = fup_date <= today
                except ValueError:
                    due = True

            if not due:
                continue

            eligible.append({k: row[v] for k, v in COL.items()})
            if len(eligible) >= limit:
                break

        print(f"  Fetched {len(eligible)} eligible leads (limit={limit})")
        return eligible

    except Exception as exc:
        print(f"  fetch_eligible_leads error: {exc}")
        return []


# ─── SCHEDULE: post-call follow-up update ────────────────────────────────────

def schedule_followup(phone: str, outcome: str, new_followup_date: str = "") -> bool:
    """
    After a call completes, update CRM with new outcome, next follow-up date,
    and increment follow-up count.
    Tries update first; if lead not found, does nothing (new lead should use push_to_crm).
    """
    now      = datetime.now()
    next_fup = new_followup_date or _next_followup(outcome)

    updates = {
        "lead_status":    _STATUS_MAP.get(outcome, "Contacted"),
        "call_status":    _CALL_STATUS_MAP.get(outcome, "Connected"),
        "call_outcome":   outcome,
        "last_call_date": now.strftime("%Y-%m-%d"),
        "last_call_time": now.strftime("%H:%M:%S"),
        "next_followup":  next_fup,
        "counselor_needed": "Yes" if outcome in _NEEDS_COUNSELOR else "No",
    }
    return update_lead_in_crm(phone, updates)
