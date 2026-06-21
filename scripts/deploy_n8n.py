"""Deploy complete n8n workflow for Student_Supervise CRM automation."""
import json, requests, os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

# SSL bypass (Windows)
import urllib3, ssl
urllib3.disable_warnings()
os.environ["REQUESTS_CA_BUNDLE"] = ""
import requests as _req
_orig = _req.Session.send
def _no_verify(self, r, **kw):
    kw["verify"] = False
    return _orig(self, r, **kw)
_req.Session.send = _no_verify

N8N_URL  = "https://n8n.skillseba.com"
N8N_KEY  = os.getenv("N8N_API_KEY")
WF_ID    = "qKucOTYAiQulEhc3"
HEADERS  = {"X-N8N-API-KEY": N8N_KEY, "Content-Type": "application/json"}

PRIVATE_KEY = open("credentials/google_service_account.json").read()
pk = json.loads(PRIVATE_KEY)["private_key"]

# ── Code Node: JWT → access_token + prepare sheet row ──────────────────────
CODE_JS = r"""
const crypto = require('crypto');
const SA_EMAIL  = "emailautomation@pricetracker-487006.iam.gserviceaccount.com";
const SHEET_ID  = "1BpnN88jQHOY5gLi1JcVopVFg6pOWfOR2jwn6flX2pdA";
const PRIV_KEY  = `""" + pk.replace("`", r"\`") + r"""`;

const data = $input.first().json;

// Build JWT
const now = Math.floor(Date.now() / 1000);
const hdr = Buffer.from(JSON.stringify({alg:"RS256",typ:"JWT"})).toString("base64url");
const pld = Buffer.from(JSON.stringify({
  iss: SA_EMAIL,
  scope: "https://www.googleapis.com/auth/spreadsheets",
  aud: "https://oauth2.googleapis.com/token",
  exp: now + 3600, iat: now
})).toString("base64url");
const signer = crypto.createSign("RSA-SHA256");
signer.update(hdr + "." + pld);
const jwt = hdr + "." + pld + "." + signer.sign(PRIV_KEY, "base64url");

// Exchange for access token (using fetch - native Node.js 18+)
const tokenRes = await fetch("https://oauth2.googleapis.com/token", {
  method: "POST",
  headers: {"Content-Type": "application/x-www-form-urlencoded"},
  body: "grant_type=urn%3Aietf%3Aparams%3Aoauth%3Agrant-type%3Ajwt-bearer&assertion=" + jwt
});
const tokenJson = await tokenRes.json();
const accessToken = tokenJson.access_token;

// Outcome → sheet field mapping
const MAP = {
  highly_interested: {s:"Highly Interested", i:"High",   p:"80%", v:"Yes"},
  interested:        {s:"Interested",        i:"Medium", p:"50%", v:"Pending"},
  busy:              {s:"Busy/Call Later",   i:"Medium", p:"50%", v:"Pending"},
  not_interested:    {s:"Not Interested",    i:"Low",    p:"0%",  v:"Pending"},
  no_answer:         {s:"No Answer",         i:"None",   p:"20%", v:"Pending"},
  visit_scheduled:   {s:"Callback Scheduled",i:"High",   p:"80%", v:"Yes"},
  wants_human:       {s:"Human Escalated",  i:"High",   p:"50%", v:"Pending"},
};
const m = MAP[data.call_outcome] || {s:"New Lead",i:"None",p:"20%",v:"Pending"};

// Next follow-up date
const d = new Date();
if      (data.call_outcome === "not_interested") d.setDate(d.getDate()+15);
else if (data.call_outcome === "busy")           d.setHours(d.getHours()+4);
else if (data.call_outcome === "no_answer")      d.setDate(d.getDate()+1);
else if (data.call_outcome === "interested")     d.setDate(d.getDate()+2);
const nextFup = d.toISOString().split("T")[0];

const leadId = "MA-LEAD-" + String(Math.floor(1000 + Math.random()*9000));

const row = [
  leadId,
  data.student_name    || "",
  data.parent_name     || "",
  data.phone           || "",
  data.class_interested|| "",
  "AI Voice Call",
  m.s, m.i,
  data.language || "Hindi",
  nextFup, 1, m.v, m.p,
  (data.ai_summary||"").substring(0,500),
  "", "", "Outbound"
];

return [{ json: { access_token: accessToken, row, sheet_id: SHEET_ID, lead_id: leadId, outcome: data.call_outcome } }];
"""

# ── Workflow definition ─────────────────────────────────────────────────────
workflow = {
    "name": "Student_Supervise — CRM Auto-Update",
    "nodes": [
        {
            "id": "n1", "name": "Webhook — Receive Call Outcome",
            "type": "n8n-nodes-base.webhook",
            "typeVersion": 2, "position": [200, 300],
            "parameters": {
                "httpMethod": "POST",
                "path": "f6ac68e6-71f7-460f-8f48-34d28783d5c2",
                "responseMode": "onReceived",
                "responseData": "firstEntryJson",
                "options": {}
            },
            "webhookId": "f6ac68e6-71f7-460f-8f48-34d28783d5c2"
        },
        {
            "id": "n2", "name": "JWT Auth + Prepare Row",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2, "position": [480, 300],
            "parameters": {"mode": "runOnceForAllItems", "jsCode": CODE_JS}
        },
        {
            "id": "n3", "name": "Google Sheets — Append Row",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.2, "position": [760, 300],
            "parameters": {
                "method": "POST",
                "url": "=https://sheets.googleapis.com/v4/spreadsheets/{{ $json.sheet_id }}/values/Lead%20Management!A%3AQ:append?valueInputOption=USER_ENTERED&insertDataOption=INSERT_ROWS",
                "authentication": "none",
                "sendHeaders": True,
                "headerParameters": {
                    "parameters": [{"name": "Authorization", "value": "=Bearer {{ $json.access_token }}"}]
                },
                "sendBody": True,
                "specifyBody": "json",
                "jsonBody": "={\"values\":[{{ JSON.stringify($json.row) }}]}",
                "options": {}
            }
        },
    ],
    "connections": {
        "Webhook — Receive Call Outcome": {"main": [[{"node": "JWT Auth + Prepare Row",     "type": "main", "index": 0}]]},
        "JWT Auth + Prepare Row":         {"main": [[{"node": "Google Sheets — Append Row", "type": "main", "index": 0}]]},
    },
    "settings": {"executionOrder": "v1"}
}

# ── Deploy ─────────────────────────────────────────────────────────────────
print("Deploying workflow to n8n...")
resp = requests.put(
    f"{N8N_URL}/api/v1/workflows/{WF_ID}",
    headers=HEADERS,
    json=workflow
)
if resp.status_code == 200:
    data = resp.json()
    print(f"Workflow updated! Nodes: {len(data.get('nodes', []))}")
    for n in data.get("nodes", []):
        print(f"  - {n['name']}")
    # Activate
    act = requests.post(f"{N8N_URL}/api/v1/workflows/{WF_ID}/activate", headers=HEADERS)
    print(f"Activated: {act.json().get('active', False)}")
else:
    print(f"Error {resp.status_code}: {resp.text[:500]}")
