import sys
import os

# Add src to path
sys.path.append(os.path.abspath('src'))

from crm_updater import push_to_crm

if __name__ == "__main__":
    result = push_to_crm(
        phone="+919876543210",
        call_outcome="interested",
        ai_summary="Test summary",
        language="en",
        recording_link="http://test.com/recording.mp3"
    )
    print(f"CRM Push Result: {result}")
