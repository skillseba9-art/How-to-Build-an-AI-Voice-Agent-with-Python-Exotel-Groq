# Production Handoff — Exotel + n8n + CRM Flow

This file is a minimal handoff note for the production path of the current project.
It documents how the existing codebase can be run with real Exotel voice calling and how to validate the flow.

## What is currently implemented
- n8n workflow: Outbound Call Handler — Modern Academy
- CRM bridge: src/webhook_server.py
- AI voice/assistant logic: src/voice_agent.py, src/ai_brain.py, src/stt.py, src/tts.py
- WhatsApp demo bridge: whatsapp_bot/index.js and src/whatsapp_server.py

## What is now wired for real production calling
The outbound workflow now uses the real Exotel call path in scripts/deploy_n8n_workflows.py.
It expects these values in .env:
1. EXOTEL_SID
2. EXOTEL_API_KEY
3. EXOTEL_FROM
4. EXOTEL_BASE_URL
5. EXOTEL_TWIML_URL

The node will attempt to call Exotel directly and return the result to n8n / CRM.

## Required provider values
Set these in .env:
- EXOTEL_SID
- EXOTEL_API_KEY
- EXOTEL_FROM
- EXOTEL_BASE_URL
- EXOTEL_TWIML_URL

## How the real flow works
1. A lead is sent to the n8n webhook: /webhook/outbound-call
2. n8n validates the phone number and prepares the lead
3. n8n calls Exotel to start the phone call
4. Exotel connects the caller to the live voice pipeline
5. n8n updates CRM via the webhook server

## How to test before production
1. Start the webhook server:
   venv\Scripts\python src\webhook_server.py
2. Run the deployment script:
   venv\Scripts\python scripts\deploy_n8n_workflows.py
3. Send a test POST to the outbound webhook:
   curl -X POST "https://n8n.skillseba.com/webhook/outbound-call" -H "Content-Type: application/json" -d "{\"phone\":\"+919876543210\",\"parent_name\":\"Test Parent\",\"student_name\":\"Test Student\",\"language\":\"Hindi\"}"
4. Confirm the response contains success:true and a call_id
5. Confirm CRM updates in Google Sheets

## Notes for the person who will run it
- No project logic change is needed for the handoff itself.
- Only provider credentials and the Exotel HTTP Request node need to be configured.
- The current project already contains the webhook bridge, CRM updates, and the n8n deployment path.
