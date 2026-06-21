# 🎓 Modern Academy AI Voice Agent

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)
![LLM](https://img.shields.io/badge/LLM-Groq_Llama3-orange.svg)
![Automation](https://img.shields.io/badge/Automation-n8n-red.svg)

An end-to-end Bilingual (Hindi & English) AI Voice Agent designed for the admission department of Modern Academy. This system answers queries, detects caller intent, schedules follow-ups, saves lead details directly to Google Sheets CRM, and triggers automated WhatsApp follow-up messages using n8n.

---

## ✨ Key Features
- **Conversational Voice AI**: Uses Groq Whisper (STT), Llama 3 (LLM), and Edge-TTS for real-time voice interactions.
- **RAG Implementation**: ChromaDB vector store powers the AI's knowledge base (`school_info.txt`) to ensure zero hallucinations.
- **Bilingual Support**: Automatically detects and switches between English and Hindi based on the caller's input.
- **Smart Intent Detection**: Classifies calls as `Highly Interested`, `Interested`, `Busy`, or `Not Interested`.
- **Automated CRM**: Pushes call summaries, duration, and outcomes to a Google Sheet using Google Service Accounts.
- **n8n Automation**: Webhook triggers post-call WhatsApp alerts to both the lead and the admin counselor.

---

## 📂 Project Structure

```text
Student_Supervise/
├── .env                              # Environment variables (API Keys, Webhooks)
├── requirements.txt                  # Python dependencies
├── src/
│   ├── ai_brain.py                   # LLM & RAG Integration
│   ├── rag_pipeline.py               # ChromaDB embeddings & indexing
│   ├── stt.py                        # Speech-to-Text using Groq Whisper
│   ├── tts.py                        # Text-to-Speech using Edge-TTS
│   ├── voice_agent.py                # Main conversation loop & intent detection
│   ├── crm_updater.py                # Google Sheets read/write operations
│   └── webhook_server.py             # FastAPI server for n8n/Telephony integration
├── knowledge_base/
│   └── school_info.txt               # Raw text data for the RAG model
├── credentials/
│   └── google_service_account.json   # Service account key for Google Sheets CRM
└── scripts/
    └── deploy_n8n_workflows.py       # Script to auto-deploy workflows to n8n
```

---

## ⚙️ Installation & Setup

### 1. Prerequisites
- Python 3.10+
- A Google Cloud Project with Google Sheets/Drive API enabled.
- Groq API Key
- n8n Server (Local or Cloud)

### 2. Environment Setup
Clone the repository and set up a virtual environment:
```bash
python -m venv venv
venv\Scripts\activate   # On Mac/Linux: source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configuration
1. Rename `.env.example` to `.env` and fill in your API keys (Groq, Exotel, n8n, etc.).
2. Place your `google_service_account.json` file inside the `credentials/` folder.
3. Share your target Google Sheet with the email address located in your service account JSON file.

---

## 🚀 Running the System

### Deploy Automations
Deploy the CRM and WhatsApp follow-up workflows to your n8n server:
```bash
python scripts/deploy_n8n_workflows.py
```

### Start the Webhook Server
Starts the FastAPI server to listen for Telephony/n8n requests:
```bash
python src/webhook_server.py
```

### Run the Voice Agent (Testing)
You can interact with the agent using your microphone:
```bash
python src/voice_agent.py
```
Or test the logic quickly using Text Mode:
```bash
python src/voice_agent.py --text
```

---
**Developed for Automated Lead Management & Admissions**
