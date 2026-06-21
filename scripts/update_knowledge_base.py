"""
Update knowledge_base/school_info.txt from ALL tabs in Google Sheets
Sheet: https://docs.google.com/spreadsheets/d/1BpnN88jQHOY5gLi1JcVopVFg6pOWfOR2jwn6flX2pdA
"""

import os, sys
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

# --- Config ---
SHEET_ID = "1BpnN88jQHOY5gLi1JcVopVFg6pOWfOR2jwn6flX2pdA"
BASE_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVICE_ACCOUNT_JSON = os.path.join(BASE_DIR, "credentials", "google_service_account.json")
OUTPUT_FILE          = os.path.join(BASE_DIR, "knowledge_base", "school_info.txt")

# Tabs to SKIP (CRM/log data - not knowledge base material)
SKIP_TABS = {"Lead Management", "Interaction Logs", "Sheet1", "Leads", "CRM", "Raw Data"}

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

def get_client():
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_JSON, scopes=SCOPES)
    return gspread.authorize(creds)

def format_tab(rows, tab_title):
    """Convert a single worksheet's rows into readable KB text."""
    if not rows or len(rows) < 2:
        return ""

    headers = [h.strip() for h in rows[0]]
    data_rows = [r for r in rows[1:] if any(c.strip() for c in r)]

    if not data_rows:
        return ""

    lines = []
    lines.append(f"\n{'='*50}")
    lines.append(f"== {tab_title.upper()} ==")
    lines.append(f"{'='*50}")

    # 2-column key-value format
    if len(headers) <= 2:
        for row in data_rows:
            key = row[0].strip() if len(row) > 0 else ""
            val = row[1].strip() if len(row) > 1 else ""
            if not key and not val:
                lines.append("")
            elif not val:
                lines.append(f"\n[{key}]")
            else:
                lines.append(f"{key}: {val}")

    # Multi-column table format
    else:
        for row in data_rows:
            parts = []
            for i, header in enumerate(headers):
                val = row[i].strip() if i < len(row) else ""
                if val and header:
                    parts.append(f"{header}: {val}")
            if parts:
                lines.append(". ".join(parts) + ".")

    return "\n".join(lines)

def main():
    print("=" * 60)
    print("  Knowledge Base Builder — Modern Academy (All Tabs)")
    print("=" * 60)

    print("\n[1/4] Connecting to Google Sheets...")
    client = get_client()
    spreadsheet = client.open_by_key(SHEET_ID)
    all_worksheets = spreadsheet.worksheets()
    print(f"      Spreadsheet: '{spreadsheet.title}'")
    print(f"      Total tabs found: {len(all_worksheets)}")

    # List all tabs
    print("\n      Tabs in this spreadsheet:")
    for ws in all_worksheets:
        skip_flag = " [SKIP]" if ws.title in SKIP_TABS else " [READ]"
        print(f"        - '{ws.title}' (gid={ws.id}){skip_flag}")

    print("\n[2/4] Reading all knowledge tabs...")
    all_sections = []
    read_count = 0

    for ws in all_worksheets:
        if ws.title in SKIP_TABS:
            print(f"      Skipping: '{ws.title}'")
            continue

        try:
            rows = ws.get_all_values()
            section = format_tab(rows, ws.title)
            if section.strip():
                all_sections.append(section)
                print(f"      Read OK:  '{ws.title}' ({len(rows)} rows)")
                read_count += 1
            else:
                print(f"      Empty:    '{ws.title}' (no usable data)")
        except Exception as e:
            print(f"      ERROR:    '{ws.title}' -> {e}")

    if not all_sections:
        print("\n[ERROR] No usable content found in any tab!")
        sys.exit(1)

    print(f"\n[3/4] Generating school_info.txt from {read_count} tabs...")

    header = f"""MODERN ACADEMY — SCHOOL KNOWLEDGE BASE
Generated from Google Sheets on {datetime.now().strftime('%Y-%m-%d %H:%M')}
This file is used by the AI Voice Agent (RAG system) to answer admission queries.
{'='*60}
"""
    full_content = header + "\n".join(all_sections) + "\n"

    # Backup old file
    if os.path.exists(OUTPUT_FILE):
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup = OUTPUT_FILE.replace(".txt", f"_backup_{ts}.txt")
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            old = f.read()
        with open(backup, "w", encoding="utf-8") as f:
            f.write(old)
        print(f"      Backup saved: knowledge_base/{os.path.basename(backup)}")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(full_content)

    print(f"\n[4/4] File written successfully!")
    print(f"      Path : {OUTPUT_FILE}")
    print(f"      Size : {len(full_content)} bytes")
    print(f"      Lines: {len(full_content.splitlines())}")
    print(f"      Tabs : {read_count} sections merged")

    print("\n--- Preview (first 30 lines) ---")
    for line in full_content.splitlines()[:30]:
        print(f"  {line}")

    print("\nDone! Now restart voice_agent.py to reload the knowledge base.")
    print("The ChromaDB RAG index will auto-rebuild on next startup.")

if __name__ == "__main__":
    main()
