# ✅ Task Plan — AI Voice Admission Agent (Mock Project)

> **Project:** Modern Academy — AI Voice Calling Demo  
> **Stack:** All Free Tools  
> **Goal:** To create a working demo that can be shown to the client
> **Estimated Total Time:** ~2-3 weeks (Part-time)

---

## 🛠️ Confirmed Free Tool Stack

| # | Work tool
|---|-----|-----|
| 1 | Automation n8n (Self-hosted, Local) |
| 2 | LLM | GROQ Free Tier (Llama-3.3-70B) |
| 3 | STT | GROQ Whisper API (Free Tier) |
| 4 | TTS | Edge-TTS (Microsoft, completely free) |
| 5 | Voice Interface | Browser Microphone (WebRTC Simulate) |
| 6 | Vector DB | ChromaDB (Local) or Pinecone Free
| 7 | Embeddings | Sentence Transformers (Local Python) |
| 8 | CRM | Google Sheets |

---

## 📋 Phase Overview

```
Phase 1 → Environment Setup (3-4 days)
Phase 2 → Knowledge Base (RAG) (3-4 days)
Phase 3 → AI Voice Pipeline (4-5 days)
Phase 4 → n8n Workflow Build (3-4 days)
Phase 5 → Demo Integration (2-3 days)
─────────────────────────────────────────────
Total ~15-20 days
```

---

## Phase 1: Environment Setup ⚙️
**Time:** 3-4 days **Goal:** Install all tools and collect API Key

### Task 1.1 — GROQ Account & API Key
- [ ] [open free account at groq.com](https://console.groq.com).
- [ ] Create API Key (Dashboard → API Keys)
- [ ] Save in `.env` file: `GROQ_API_KEY=your_key_here`
- [ ] **Test:** Say "Hello" to `llama-3.3-70b-versatile` model with cURL

```bash
curl https://api.groq.com/openai/v1/chat/completions \
  -H "Authorization: Bearer $GROQ_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"llama-3.3-70b-versatile","messages":[{"role":"user","content":"Hello"}]}'
```

**✅ If done:** JSON response is coming

---

### Task 1.2 — n8n Self-hosted Setup (Docker)
- [ ] Install Docker Desktop (if not already present)
- [ ] Run the following command:

```bash
docker run -it --rm --name n8n -p 5678:5678 \
  -v n8n_data:/home/node/.n8n n8nio/n8n
```

- [ ] Open `http://localhost:5678` in browser
- [ ] Create admin account

**✅ When Done:** n8n Dashboard is displayed

---

### Task 1.3 — Python Environment Setup
- [ ] Check Python 3.10+: `python --version`
- [ ] Create project folder: `ai-admission-agent/`
- [ ] Virtual environment:

```bash
python -m venv venv
venv\Scripts\activate   # Windows
```

- [ ] Install Libraries:

```bash
pip install groq edge-tts chromadb sentence-transformers \
            gspread oauth2client python-dotenv fastapi \
            uvicorn sounddevice numpy wave
```

**✅ If done:** All libraries installed, no error

---

### Task 1.4 — Google Sheets CRM Setup
- [ ] Create a new Google Sheet: ``Modern Academy CRM''
- [ ] Add Columns to Row 1:

```
Lead ID | Student Name | Parent Name | Phone | Class |
Lead Status | Interest Level | Call Status | Call Outcome |
Language | Last Call Date | Next Followup | AI Summary | Converted
```

- [ ] Google Cloud Console → Enable Sheets API
- [ ] Create Service Account → Download JSON key
- [ ] Share the sheet to Service Account email

**✅ If Done:** Test row is being written with Python

---

## Phase 2: Knowledge Base (RAG Pipeline) 🧠
**Time:** 3-4 days **Goal:** Empower AI with school data

### Task 2.1 — Creation of Knowledge Base Content
- [ ] Create `knowledge_base/school_info.txt` file
- [ ] Cover the following topics (Mock but Realistic):

```
✍️ Topics to cover:
- Admission Process
- Fee Structure (Class-wise fee details)
- Classes Available (LKG to Class 12)
- Facilities (Lab, Sports, Transport, Hostel)
- Documents Required (Birth Certificate, Previous TC etc.)
- School Timings
- Scholarship Details
- FAQs — Minimum 15 Q&As
```

**✅ If Done:** The file has at least 500 words

---

### Task 2.2 — Embedding + ChromaDB Setup
- [ ] Create `src/rag_pipeline.py`:

```python
from sentence_transformers import SentenceTransformer
import chromadb

model = SentenceTransformer('all-MiniLM-L6-v2')
client = chromadb.Client()
collection = client.create_collection("school_kb")

def load_kb(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()
    chunks = [c.strip() for c in text.split('\n\n') if c.strip()]
    return chunks

chunks = load_kb('knowledge_base/school_info.txt')
embeddings = model.encode(chunks).tolist()
collection.add(
    documents=chunks,
    embeddings=embeddings,
    ids=[f"chunk_{i}" for i in range(len(chunks))]
)
print(f"✅ {len(chunks)} chunks indexed!")

def query_kb(question, top_k=3):
    q_embed = model.encode([question]).tolist()
    results = collection.query(query_embeddings=q_embed, n_results=top_k)
    return "\n".join(results['documents'][0])
```

**✅ When Done:** Script run → "X chunks indexed" is displayed

---

### Task 2.3 — GROQ + RAG = AI Brain
- [ ] Create `src/ai_brain.py`:

```python
from groq import Groq
from rag_pipeline import query_kb
import os

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

SYSTEM_PROMPT = """You are an AI admission counselor for Modern Academy.
RULES:
1. Answer ONLY from the context provided
2. If answer not in context: "Let me connect you with our counselor"
3. Keep replies SHORT — max 2-3 sentences
4. Be warm, friendly, persuasive
5. Always encourage a school visit
6. Speak in {language}

Context:
{context}"""

def get_ai_response(user_message, language="Hindi", chat_history=[]):
    context = query_kb(user_message)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT.format(
            language=language, context=context)}
    ] + chat_history + [{"role": "user", "content": user_message}]
    
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        max_tokens=150,
        temperature=0.7
    )
    return response.choices[0].message.content
```

**✅ If done: ** KB-based answer is coming if you ask, no hallucination

---

## Phase 3: AI Voice Pipeline 🎙️
**Time:** 4-5 days **Target:** Mic → STT → AI → TTS → Speaker

### Task 3.1 — STT: GROQ Whisper
- [ ] Create `src/stt.py`:

```python
from groq import Groq
import os

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def transcribe_audio(audio_file_path, language="hi"):
    with open(audio_file_path, "rb") as f:
        result = client.audio.transcriptions.create(
            model="whisper-large-v3-turbo",
            file=f,
            language=language,
            response_format="text"
        )
    return result
```

**✅ If Done:** Audio file → accurate text (Hindi + English)

---

### Task 3.2 — TTS: Edge-TTS
- [ ] Create `src/tts.py`:

```python
import edge_tts, asyncio

VOICES = {
    "Hindi": "hi-IN-SwaraNeural",
    "English": "en-IN-NeerjaNeural"
}

async def _tts(text, language, output_file):
    voice = VOICES.get(language, VOICES["Hindi"])
    await edge_tts.Communicate(text, voice).save(output_file)

def speak(text, language="Hindi", output_file="output.mp3"):
    asyncio.run(_tts(text, language, output_file))
    # Play output.mp3 (with pygame or os.system)
```

**✅ If done: ** Natural voice is being created in Hindi and English

---

### Task 3.3 — Microphone Capture
- [ ] Create `src/mic_capture.py`:

```python
import sounddevice as sd
import numpy as np, wave

def record_audio(duration=7, sample_rate=16000, output_file="input.wav"):
    print(f"🎙️ Recording {duration}s...")
    audio = sd.rec(int(duration * sample_rate),
                   samplerate=sample_rate, channels=1, dtype='int16')
    sd.wait()
    with wave.open(output_file, 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio.tobytes())
    print("✅ Recorded!")
    return output_file
```

**✅ If Done:** Audio is being recorded from PC mic

---

### Task 3.4 — Full Voice Pipeline (End-to-End Test)
- [ ] Create `src/voice_agent.py`:

```python
from mic_capture import record_audio
from stt import transcribe_audio
from ai_brain import get_ai_response
from tts import speak

def run_agent():
    chat_history = []
    language = "Hindi"
    
    print("🤖 AI Admission Agent launched!")
    speak("नमस्ते! मैं Modern Academy का AI assistant हूँ।", language)
    
    while True:
        input("\n🎙️ Press Enter and speak (exit with q)...")
        audio = record_audio(duration=7)
        user_text = transcribe_audio(audio)
        
        if not user_text: continue
        print(f"👤 You: {user_text}")
        
        if "english" in user_text.lower(): language = "English"
        
        ai_text = get_ai_response(user_text, language, chat_history)
        print(f"🤖 AI: {ai_text}")
        speak(ai_text, language)
        
        chat_history += [
            {"role": "user", "content": user_text},
            {"role": "assistant", "content": ai_text}
        ]

if __name__ == "__main__":
    run_agent()
```

**✅ When Done:** Mic → AI Answer → Voice — full loop working

---

## Phase 4: n8n Workflow 🔄
**Time:** 3-4 days **Goal:** Automate CRM Update and Follow-up with n8n

### Task 4.1 — CRM Auto-Update Workflow
- [ ] n8n → New Workflow: `"CRM Auto-Update"`
- [ ] Nodes:
  1. **Webhook** → will receive call outcome from AI Agent
  2. **Google Sheets** → CRM will update the row
  3. **IF Node** → Interest level check
  4. **Set Node** → Next follow-up date set

- [ ] Add the webhook call in Python:
```python
import requests

def update_crm(lead_data: dict):
    requests.post("http://localhost:5678/webhook/crm-update", json=lead_data)
```

**✅ If Done: ** CRM is automatically updated at the end of the call

---

### Task 4.2 — Follow-up Automation Workflow
- [ ] n8n → New Workflow: `"Follow-up Scheduler"`
- [ ] Logic:

```
outcome = "interested"    → Followup = Today + 2 days
outcome = "busy"          → Followup = Today + 4 hours  
outcome = "no_answer"     → Retry Count +1 (max 3)
outcome = "not_interested"→ Mark Closed
```

**✅ If Done:** Follow-up dates are being set correctly in CRM

---

## Phase 5: Demo Ready 🎬
**Time:** 2-3 days **Goal:** Ready to show to Client

### Task 5.1 — Creating Demo Scenarios
- [ ] Practice the following 3 scenarios:

| Scenario | Flow |
|----------|------|
| **Interested Parent (Hindi)** | Fee asks → AI answers → Visit convinces → CRM updates |
| **Busy Parent (English)** | Call later → Schedule AI → Set Follow-up |
| **Complex Query → Escalation** | AI doesn't know → says "Counselor connect" → CRM mark |

---

### Task 5.2 — Final Checklist ✅

- [ ] Hindi conversation is working
- [ ] English conversation is working
- [ ] Language switch (Hindi ↔ English) is working
- [ ] Correct answer coming from KB, no hallucination
- [ ] CRM is auto-updating in Google Sheets
- [ ] Follow-up dates are being set correctly
- [ ] Response latency within 5 seconds (acceptable in Mock)
- [ ] Introducing n8n Workflows
- [ ] 3 demo scenarios are successfully presented

---

## 📁 Final Project Folder Structure

```
ai-admission-agent/
├── .env                        # GROQ_API_KEY, Google credentials
├── requirements.txt
├── knowledge_base/
│ └── school_info.txt # All school information
├── src/
│   ├── rag_pipeline.py         # ChromaDB + Embeddings
│   ├── ai_brain.py             # GROQ LLM + RAG
│   ├── stt.py                  # Groq Whisper STT
│   ├── tts.py                  # Edge-TTS
│   ├── mic_capture.py          # Microphone recording
│   ├── voice_agent.py          # Main pipeline
│   └── crm_updater.py          # Google Sheets connector
└── n8n_workflows/
    ├── crm_auto_update.json
    └── followup_scheduler.json
```

---

## ⏱️ Time Summary

| Phase | Focus | Time
|-------|-------|------|
| Phase 1 | Setup | 3-4 days
| Phase 2 | RAG + AI Brain | 3-4 days
| Phase 3 | Voice Pipeline | 4-5 days
| Phase 4 | n8n Workflows | 3-4 days
| Phase 5 | Demo Polish | 2-3 days
| **Total** | | **~15-20 Days** |

> **💡 Tip:** Start Phase 1 and Phase 2 together — Create KB content while Setup is running. Save time.
