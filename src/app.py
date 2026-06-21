import sys
sys.stdout.reconfigure(encoding='utf-8')

from mic_capture import record_audio
from stt import transcribe_audio
from ai_brain import get_ai_response
from rag_pipeline import index_knowledge_base
from tts import speak
import requests
import os

def send_to_crm(user_text, ai_reply):
    """Sending data to Google Sheet via n8n Webhook"""
    webhook_url = os.getenv("N8N_WEBHOOK_URL")
    if not webhook_url:
        return
        
    print("\n[☁️] Sending data to Google Sheet via n8n Webhook...")
    try:
        data = {
            "Phone": "Mock_User_" + str(os.urandom(2).hex()),
            "Message": user_text,
            "AI_Response": ai_reply,
            "Status": "Needs Counselor" if "counselor" in ai_reply.lower() else "Inquiry"
        }
        requests.post(webhook_url, json=data)
        print("✅ Data saved to Google Sheet!")
    except Exception as e:
        print("❌ CRM Error:", e)

def main():
    print("📚 Loading school database into memory...")
    index_knowledge_base()
    
    print("\n🤖 Modern Academy AI Admission Assistant started...")
    print("-------------------------------------------------")
    
    chat_history = []
    
    while True:
        try:
            input("\nPress [Enter] and start speaking (Press Ctrl+C to stop)...")
            
            # 1. Record audio from microphone
            audio_file = record_audio(duration=5, output_file="conversation.wav")
            
            # 2. Convert speech to text
            user_text = transcribe_audio(audio_file, language="en-IN")
            
            if not user_text:
                continue
                
            print(f"\n👤 Parent: {user_text}")
            
            # 3. Generate response using AI
            ai_reply = get_ai_response(user_text, language="English", chat_history=chat_history)
            
            # 4. Play AI speech (TTS)
            speak(ai_reply, language="English", output_file="reply.mp3")
            
            # 5. Save to Google Sheet using n8n (if lead)
            send_to_crm(user_text, ai_reply)
            
            # Save to memory
            chat_history.append({"role": "user", "content": user_text})
            chat_history.append({"role": "assistant", "content": ai_reply})
            
            # Ensure memory doesn't grow too large
            if len(chat_history) > 6:
                chat_history = chat_history[-6:]
                
        except KeyboardInterrupt:
            print("\n👋 Stopping AI Assistant...")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    main()
