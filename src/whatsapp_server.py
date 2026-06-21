from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import base64
import os

from stt import transcribe_audio
from ai_brain import get_ai_response
from tts import speak
from app import send_to_crm
from rag_pipeline import index_knowledge_base

app = FastAPI(title="WhatsApp AI Voice Bridge")

class AudioMessage(BaseModel):
    phone: str
    audio_base64: str

print("Initializing Knowledge Base for WhatsApp Server...")
index_knowledge_base()
chat_histories = {}

@app.post("/api/whatsapp-voice")
def handle_whatsapp_voice(msg: AudioMessage):
    # 1. Save incoming base64 as .ogg
    incoming_file = f"incoming_{msg.phone.split('@')[0]}.ogg"
    with open(incoming_file, "wb") as f:
        f.write(base64.b64decode(msg.audio_base64))
        
    print(f"\n[WhatsApp] Received audio from {msg.phone}")
    
    # 2. Transcribe
    user_text = transcribe_audio(incoming_file, language="en-IN")
    if not user_text:
        raise HTTPException(status_code=400, detail="Could not understand audio")
        
    print(f"👤 {msg.phone}: {user_text}")
    
    # 3. AI Brain
    history = chat_histories.get(msg.phone, [])
    ai_reply = get_ai_response(user_text, language="English", chat_history=history)
    print(f"🤖 AI: {ai_reply}")
    
    # Update history
    history.append({"role": "user", "content": user_text})
    history.append({"role": "assistant", "content": ai_reply})
    if len(history) > 6:
        history = history[-6:]
    chat_histories[msg.phone] = history
    
    # 4. TTS to .mp3
    outgoing_file = f"reply_{msg.phone.split('@')[0]}.mp3"
    speak(ai_reply, language="English", output_file=outgoing_file)
    
    # 5. CRM Push
    send_to_crm(user_text, ai_reply)
    
    # 6. Read back as base64
    with open(outgoing_file, "rb") as f:
        out_base64 = base64.b64encode(f.read()).decode('utf-8')
        
    # Cleanup files
    try:
        os.remove(incoming_file)
        os.remove(outgoing_file)
    except:
        pass
        
    return {
        "reply_text": ai_reply,
        "audio_base64": out_base64,
        "mime_type": "audio/mp3"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
