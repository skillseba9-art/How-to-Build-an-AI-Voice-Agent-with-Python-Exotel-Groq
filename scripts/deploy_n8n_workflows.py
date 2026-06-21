"""
Deploy 3 n8n workflows for Modern Academy AI Admission Agent.

Workflows:
  1. Lead Fetcher         — Cron every 30 min → fetch eligible leads → log
  2. Follow-up Scheduler  — Webhook → set next followup date → update CRM
  3. Outbound Call Handler— Webhook → route by outcome → counselor alert / follow-up

Run:
  cd Student_Supervise
  venv\\Scripts\\python scripts/deploy_n8n_workflows.py
"""

import os
import sys
import json
import requests
import urllib3
from pathlib import Path

urllib3.disable_warnings()

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

N8N_SERVER  = os.getenv("N8N_SERVER", "https://n8n.skillseba.com")
N8N_API_KEY = os.getenv("N8N_API_KEY", "")
WEBHOOK_SERVER_URL = os.getenv("WEBHOOK_SERVER_URL", "http://localhost:8000")
EXOTEL_SID = os.getenv("EXOTEL_SID", "")
EXOTEL_API_KEY = os.getenv("EXOTEL_API_KEY", "")
EXOTEL_API_TOKEN = os.getenv("EXOTEL_API_TOKEN", os.getenv("EXOTEL_TOKEN", EXOTEL_API_KEY))
EXOTEL_FROM = os.getenv("EXOTEL_FROM", "")
EXOTEL_BASE_URL = os.getenv("EXOTEL_BASE_URL", "https://api.exotel.com")
EXOTEL_TWIML_URL = os.getenv("EXOTEL_TWIML_URL", "https://example.com/exotel/voice")
WHATSAPP_API_TOKEN = os.getenv("WHATSAPP_API_TOKEN", "")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM = os.getenv("TWILIO_FROM", "")

HEADERS = {
    "X-N8N-API-KEY": N8N_API_KEY,
    "Content-Type": "application/json",
}


def api(method: str, path: str, **kwargs):
    url = f"{N8N_SERVER}/api/v1{path}"
    resp = requests.request(method, url, headers=HEADERS, verify=False, timeout=30, **kwargs)
    if not resp.ok:
        print(f"  API error {resp.status_code}: {resp.text[:300]}")
    return resp


def delete_workflow_by_name(name: str) -> None:
    existing = api("GET", "/workflows?limit=100")
    if not existing.ok:
        return
    for wf in existing.json().get("data", []):
        if wf.get("name") == name:
            wf_id = wf.get("id")
            print(f"  Deleting old workflow: {name} (id={wf_id})")
            api("DELETE", f"/workflows/{wf_id}")
            return


def deploy_workflow(workflow: dict) -> str | None:
    name = workflow.get("name", "?")
    print(f"\nDeploying: {name}")

    # Check if workflow already exists
    existing = api("GET", "/workflows?limit=50")
    if existing.ok:
        for wf in existing.json().get("data", []):
            if wf.get("name") == name:
                wf_id = wf["id"]
                print(f"  Exists (id={wf_id}), updating...")
                workflow_no_active = {k: v for k, v in workflow.items() if k != "active"}
                r = api("PUT", f"/workflows/{wf_id}", json=workflow_no_active)
                if r.ok:
                    api("POST", f"/workflows/{wf_id}/activate")
                    print(f"  Updated & activated OK")
                    return wf_id
                return None

    # Create new
    r = api("POST", "/workflows", json=workflow)
    if not r.ok:
        return None
    wf_id = r.json().get("id")
    print(f"  Created (id={wf_id})")
    api("POST", f"/workflows/{wf_id}/activate")
    print(f"  Activated OK")
    return wf_id


# ═══════════════════════════════════════════════════════════════════
# WORKFLOW 1: Lead Fetcher (Cron)
# Runs every 30 min during business hours.
# Calls Python webhook → gets eligible leads → logs count.
# ═══════════════════════════════════════════════════════════════════

LEAD_FETCHER = {
    "name": "Lead Fetcher — Modern Academy",
    "nodes": [
        {
            "id": "cron-trigger",
            "name": "Every 30 Min (Business Hours)",
            "type": "n8n-nodes-base.scheduleTrigger",
            "typeVersion": 1.1,
            "position": [200, 300],
            "parameters": {
                "rule": {
                    "interval": [
                        {
                            "field": "minutes",
                            "minutesInterval": 30,
                        }
                    ]
                }
            },
        },
        {
            "id": "fetch-leads",
            "name": "Fetch Eligible Leads",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.2,
            "position": [440, 300],
            "parameters": {
                "method": "GET",
                "url": f"{WEBHOOK_SERVER_URL}/leads/fetch",
                "sendQuery": True,
                "queryParameters": {
                    "parameters": [{"name": "limit", "value": "20"}]
                },
                "options": {"timeout": 30000},
            },
        },
        {
            "id": "check-leads",
            "name": "Any Leads Due?",
            "type": "n8n-nodes-base.if",
            "typeVersion": 2,
            "position": [680, 300],
            "parameters": {
                "conditions": {
                    "options": {"caseSensitive": True},
                    "conditions": [
                        {
                            "id": "has-leads",
                            "leftValue": "={{ $json.count }}",
                            "rightValue": 0,
                            "operator": {"type": "number", "operation": "gt"},
                        }
                    ],
                }
            },
        },
        {
            "id": "log-leads",
            "name": "Log — Leads Ready",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [920, 200],
            "parameters": {
                "jsCode": """
const data = $input.first().json;
const leads = data.leads || [];
const summary = leads.map(l =>
  `${l.phone} | ${l.lead_status} | followup#${l.followup_count}`
).join('\\n');
console.log(`[Lead Fetcher] ${leads.length} lead(s) due:\\n${summary}`);
return leads.map(l => ({ json: l }));
"""
            },
        },
        {
            "id": "log-no-leads",
            "name": "Log — No Leads Due",
            "type": "n8n-nodes-base.noOp",
            "typeVersion": 1,
            "position": [920, 420],
            "parameters": {},
        },
    ],
    "connections": {
        "Every 30 Min (Business Hours)": {
            "main": [[{"node": "Fetch Eligible Leads", "type": "main", "index": 0}]]
        },
        "Fetch Eligible Leads": {
            "main": [[{"node": "Any Leads Due?", "type": "main", "index": 0}]]
        },
        "Any Leads Due?": {
            "main": [
                [{"node": "Log — Leads Ready",   "type": "main", "index": 0}],
                [{"node": "Log — No Leads Due",  "type": "main", "index": 0}],
            ]
        },
    },
    "settings": {"executionOrder": "v1"},
}


# ═══════════════════════════════════════════════════════════════════
# WORKFLOW 2: Follow-up Scheduler (Webhook)
# Triggered by Python after each call.
# Updates CRM with new follow-up date based on outcome.
# ═══════════════════════════════════════════════════════════════════

FOLLOWUP_SCHEDULER = {
    "name": "Follow-up Scheduler — Modern Academy",
    "nodes": [
        {
            "id": "webhook-in",
            "name": "Webhook — Call Completed",
            "type": "n8n-nodes-base.webhook",
            "typeVersion": 2.1,
            "position": [200, 300],
            "webhookId": "followup-scheduler-v1",
            "parameters": {
                "path":           "followup-scheduler",
                "httpMethod":     "POST",
                "responseMode":   "responseNode",
                "responseData":   "allEntries",
            },
        },
        {
            "id": "calc-followup",
            "name": "Calculate Follow-up",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [460, 300],
            "parameters": {
                "jsCode": """
const body   = $input.first().json.body || $input.first().json;
const phone  = body.phone   || '';
const outcome= body.outcome || 'no_answer';

const FOLLOWUP_DAYS = {
  interested:        2,
  highly_interested: 0,
  busy:              0,   // 4 hours
  no_answer:         1,
  not_interested:    15,
  visit_scheduled:   1,
  wants_human:       0,
  wrong_number:      999,
  already_admitted:  999,
};

const STATUS_MAP = {
  interested:        'Interested',
  highly_interested: 'Highly Interested',
  busy:              'Busy/Call Later',
  not_interested:    'Not Interested',
  no_answer:         'No Answer',
  visit_scheduled:   'Callback Scheduled',
  wants_human:       'Human Escalated',
  wrong_number:      'Invalid',
  already_admitted:  'Admission Completed',
};

const now = new Date();
let nextDate = '';

if (outcome === 'busy') {
  const d = new Date(now.getTime() + 4*60*60*1000);
  nextDate = d.toISOString().slice(0,16).replace('T',' ');
} else {
  const days = FOLLOWUP_DAYS[outcome] ?? 2;
  if (days < 999) {
    const d = new Date(now.getTime() + days*24*60*60*1000);
    nextDate = d.toISOString().slice(0,10);
  }
}

const isHighPriority = ['highly_interested','wants_human','visit_scheduled'].includes(outcome);
const isClosed       = ['not_interested','wrong_number','already_admitted'].includes(outcome);

return [{
  json: {
    phone,
    outcome,
    lead_status:   STATUS_MAP[outcome] || 'Contacted',
    next_followup: nextDate,
    is_high_priority: isHighPriority,
    is_closed:        isClosed,
    processed_at: now.toISOString(),
  }
}];
"""
            },
        },
        {
            "id": "update-crm",
            "name": "Update CRM via Python",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.2,
            "position": [700, 300],
            "parameters": {
                "method": "POST",
                "url": f"{WEBHOOK_SERVER_URL}/leads/schedule-followup",
                "sendBody": True,
                "contentType": "json",
                "body": "={{ JSON.stringify({ phone: $json.phone, outcome: $json.outcome, new_followup_date: $json.next_followup }) }}",
                "options": {"timeout": 15000},
            },
        },
        {
            "id": "route-priority",
            "name": "High Priority?",
            "type": "n8n-nodes-base.if",
            "typeVersion": 2,
            "position": [940, 300],
            "parameters": {
                "conditions": {
                    "conditions": [
                        {
                            "id": "check-priority",
                            "leftValue": "={{ $('Calculate Follow-up').item.json.is_high_priority }}",
                            "rightValue": True,
                            "operator": {"type": "boolean", "operation": "true"},
                        }
                    ]
                }
            },
        },
        {
            "id": "alert-counselor",
            "name": "WhatsApp — Alert Admin",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.2,
            "position": [1180, 200],
            "parameters": {
                "method": "POST",
                "url": "https://api.your-whatsapp-provider.com/v1/messages",
                "sendBody": True,
                "contentType": "json",
                "body": "={{ JSON.stringify({ to: 'ADMIN_NUMBER_HERE', text: `[New Lead Alert]\\nPhone: ${$('Calculate Follow-up').item.json.phone}\\nInterest: ${$('Calculate Follow-up').item.json.outcome}\\nThey showed interest in admission. Please follow up.` }) }}",
                "options": {},
            },
        },
        {
            "id": "whatsapp-caller",
            "name": "WhatsApp — Send to Caller",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.2,
            "position": [900, 150],
            "parameters": {
                "method": "POST",
                "url": "https://api.your-whatsapp-provider.com/v1/messages",
                "sendBody": True,
                "contentType": "json",
                "body": "={{ JSON.stringify({ to: $('Calculate Follow-up').item.json.phone, text: 'Hello from Modern Academy! Thank you for your interest. For admission details, please visit our campus or reply to this message.' }) }}",
                "options": {},
            },
        },
        {
            "id": "standard-log",
            "name": "Log — Follow-up Scheduled",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [1180, 420],
            "parameters": {
                "jsCode": """
const data = $('Calculate Follow-up').item.json;
console.log(`[Follow-up Scheduled] ${data.phone} → ${data.outcome} → Next: ${data.next_followup}`);
return [{ json: { ...data, logged: true } }];
"""
            },
        },
        {
            "id": "respond-ok",
            "name": "Respond 200 OK",
            "type": "n8n-nodes-base.respondToWebhook",
            "typeVersion": 1,
            "position": [700, 500],
            "parameters": {
                "respondWith": "json",
                "responseBody": "={{ JSON.stringify({ success: true, phone: $('Calculate Follow-up').item.json.phone, next_followup: $('Calculate Follow-up').item.json.next_followup }) }}",
                "options": {"responseCode": 200},
            },
        },
    ],
    "connections": {
        "Webhook — Call Completed": {
            "main": [[{"node": "Calculate Follow-up", "type": "main", "index": 0}]]
        },
        "Calculate Follow-up": {
            "main": [[
                {"node": "Update CRM via Python",     "type": "main", "index": 0},
                {"node": "Respond 200 OK",             "type": "main", "index": 0},
            ]]
        },
        "Update CRM via Python": {
            "main": [[{"node": "WhatsApp — Send to Caller", "type": "main", "index": 0}]]
        },
        "WhatsApp — Send to Caller": {
            "main": [[{"node": "High Priority?", "type": "main", "index": 0}]]
        },
        "High Priority?": {
            "main": [
                [{"node": "WhatsApp — Alert Admin",       "type": "main", "index": 0}],
                [{"node": "Log — Follow-up Scheduled",    "type": "main", "index": 0}],
            ]
        },
    },
    "settings": {"executionOrder": "v1"},
}


# ═══════════════════════════════════════════════════════════════════
# WORKFLOW 3: Outbound Call Handler (Webhook, telephony-ready)
# Receives lead data, routes by outcome type, prepares for call.
# The telephony node now uses Exotel credentials from .env when available.
# ═══════════════════════════════════════════════════════════════════

OUTBOUND_HANDLER = {
    "name": "Outbound Call Handler — Modern Academy",
    "nodes": [
        {
            "id": "webhook-trigger",
            "name": "Webhook — Initiate Call",
            "type": "n8n-nodes-base.webhook",
            "typeVersion": 2.1,
            "position": [200, 300],
            "webhookId": "outbound-handler-v1",
            "parameters": {
                "path":         "outbound-call",
                "httpMethod":   "POST",
                "responseMode": "responseNode",
                "responseData": "allEntries",
            },
        },
        {
            "id": "validate-lead",
            "name": "Validate & Prepare Lead",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [440, 300],
            "parameters": {
                "jsCode": """
const body = $input.first().json.body || $input.first().json;

// Validate required fields
if (!body.phone) throw new Error('phone is required');

const phone = String(body.phone).trim();

// Normalize phone to +91XXXXXXXXXX
const normalizePhone = (p) => {
  p = p.replace(/\\s|-/g, '');
  if (p.startsWith('+91')) return p;
  if (p.startsWith('91') && p.length === 12) return '+' + p;
  if (p.length === 10) return '+91' + p;
  return p;
};

const normalizedPhone = normalizePhone(phone);
const isValid = /^\\+91[6-9]\\d{9}$/.test(normalizedPhone);

return [{
  json: {
    phone:           normalizedPhone,
    original_phone:  phone,
    is_valid:        isValid,
    student_name:    body.student_name    || '',
    parent_name:     body.parent_name     || '',
    class_interested:body.class_interested|| '',
    language:        body.language        || 'Hindi',
    followup_count:  parseInt(body.followup_count || 0),
    lead_status:     body.lead_status     || 'New Lead',
    prepared_at:     new Date().toISOString(),
  }
}];
"""
            },
        },
        {
            "id": "check-valid",
            "name": "Valid Phone?",
            "type": "n8n-nodes-base.if",
            "typeVersion": 2,
            "position": [680, 300],
            "parameters": {
                "conditions": {
                    "conditions": [
                        {
                            "id": "valid-check",
                            "leftValue": "={{ $json.is_valid }}",
                            "rightValue": True,
                            "operator": {"type": "boolean", "operation": "true"},
                        }
                    ]
                }
            },
        },
        {
            "id": "telephony-exotel",
            "name": "Telephony — Exotel Call",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [920, 180],
            "parameters": {
                "jsCode": """
const lead = $input.first().json;
const sid = "" + "${EXOTEL_SID}";
const apiKey = "" + "${EXOTEL_API_KEY}";
const apiToken = "" + "${EXOTEL_API_TOKEN}";
const callerId = "" + "${EXOTEL_FROM}";
const baseUrl = "" + "${EXOTEL_BASE_URL}";
const twimlUrl = "" + "${EXOTEL_TWIML_URL}";

const placeholder = ['your_exotel_caller_id_here','your_exotel_sid_here','your_exotel_api_key_here','your_exotel_api_token_here'];
if (!sid || !apiKey || !apiToken || !callerId || placeholder.includes(callerId) || placeholder.includes(sid) || placeholder.includes(apiKey) || placeholder.includes(apiToken)) {
  return [{ json: { ...lead, call_initiated: false, call_status: 'not_configured', error: 'Exotel credentials are still placeholder values. Set real EXOTEL_SID, EXOTEL_API_KEY, EXOTEL_API_TOKEN and EXOTEL_FROM in .env before a live call.' } }];
}

const url = `${baseUrl}/v1/Accounts/${sid}/Calls/connect.json`;
const payload = {
  From: callerId,
  To: lead.phone,
  CallerId: callerId,
  Url: twimlUrl
};

const auth = 'Basic ' + Buffer.from(`${apiKey}:${apiToken}`).toString('base64');

try {
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': auth,
    },
    body: JSON.stringify(payload),
  });

  const text = await res.text();
  let parsed = {};
  try { parsed = JSON.parse(text); } catch (e) { parsed = { raw: text }; }

  return [{ json: {
    ...lead,
    call_initiated: res.ok,
    call_status: res.ok ? 'initiated' : 'failed',
    exotel_status: res.status,
    exotel_response: parsed,
    call_id: parsed.call_id || `EXO-${Date.now()}`,
    exotel_error: res.ok ? '' : text,
  } }];
} catch (err) {
  return [{ json: { ...lead, call_initiated: false, call_status: 'error', exotel_error: String(err) } }];
}
"""
            },
        },
        {
            "id": "invalid-phone",
            "name": "Log — Invalid Phone",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [920, 440],
            "parameters": {
                "jsCode": """
const lead = $input.first().json;
console.log(`[Invalid Phone] Skipping: ${lead.original_phone}`);
// TODO: Update CRM to mark as Invalid
return [{ json: { ...lead, skipped: true, reason: 'invalid_phone' } }];
"""
            },
        },
        {
            "id": "update-crm-initiated",
            "name": "Update CRM — Call Initiated",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.2,
            "position": [1160, 180],
            "parameters": {
                "method": "POST",
                "url": f"{WEBHOOK_SERVER_URL}/leads/update",
                "sendBody": True,
                "contentType": "json",
                "body": """={{ JSON.stringify({
  phone: $json.phone,
  updates: {
    call_status: 'Dialing',
    last_call_date: new Date().toISOString().slice(0,10),
    last_call_time: new Date().toTimeString().slice(0,8)
  }
}) }}""",
                "options": {"timeout": 15000},
            },
        },
        {
            "id": "respond-call-initiated",
            "name": "Respond — Call Initiated",
            "type": "n8n-nodes-base.respondToWebhook",
            "typeVersion": 1,
            "position": [1160, 320],
            "parameters": {
                "respondWith": "json",
                "responseBody": "={{ JSON.stringify({ success: true, phone: $('Validate & Prepare Lead').item.json.phone, call_id: $('Telephony — Exotel Call').item.json.call_id }) }}",
                "options": {"responseCode": 200},
            },
        },
    ],
    "connections": {
        "Webhook — Initiate Call": {
            "main": [[{"node": "Validate & Prepare Lead", "type": "main", "index": 0}]]
        },
        "Validate & Prepare Lead": {
            "main": [[{"node": "Valid Phone?", "type": "main", "index": 0}]]
        },
        "Valid Phone?": {
            "main": [
                [{"node": "Telephony — Exotel Call", "type": "main", "index": 0}],
                [{"node": "Log — Invalid Phone",                       "type": "main", "index": 0}],
            ]
        },
        "Telephony — Exotel Call": {
            "main": [[{"node": "Update CRM — Call Initiated", "type": "main", "index": 0}]]
        },
    },
    "settings": {"executionOrder": "v1"},
}


# ─── Deploy all ───────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  n8n Workflow Deployment — Modern Academy")
    print(f"  Server: {N8N_SERVER}")
    print("=" * 60)

    if not N8N_API_KEY:
        print("ERROR: N8N_API_KEY not found in .env")
        sys.exit(1)

    for old_name in ["Lead Fetcher — Modern Academy", "Follow-up Scheduler — Modern Academy"]:
        delete_workflow_by_name(old_name)

    results = {}
    for wf in [LEAD_FETCHER, FOLLOWUP_SCHEDULER, OUTBOUND_HANDLER]:
        wf_id = deploy_workflow(wf)
        results[wf["name"]] = wf_id or "FAILED"

    print("\n" + "=" * 60)
    print("  Deployment Summary")
    print("=" * 60)
    for name, wf_id in results.items():
        status = "[OK]" if wf_id != "FAILED" else "[FAIL]"
        print(f"  {status} {name}")
        if wf_id != "FAILED":
            print(f"      ID: {wf_id}")
            if "Follow-up" in name:
                print(f"      Webhook: {N8N_SERVER}/webhook/followup-scheduler")
            elif "Outbound" in name:
                print(f"      Webhook: {N8N_SERVER}/webhook/outbound-call")

    print("\nWebhook Server URLs for n8n:")
    print(f"  Start server: venv\\Scripts\\python src/webhook_server.py")
    print(f"  Health check: {WEBHOOK_SERVER_URL}/health")
    print(f"  Docs:         {WEBHOOK_SERVER_URL}/docs")
    print("\nActive workflow: Only the outbound call workflow is deployed now.")
    print("=" * 60)


if __name__ == "__main__":
    main()
