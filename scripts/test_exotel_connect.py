import os
import base64
import requests
from dotenv import load_dotenv

load_dotenv('.env')

sid = os.getenv('EXOTEL_SID', '')
api_key = os.getenv('EXOTEL_API_KEY', '')
token = os.getenv('EXOTEL_API_TOKEN', '') or os.getenv('EXOTEL_TOKEN', '')
caller = os.getenv('EXOTEL_FROM', '')

PLACEHOLDER_VALUES = {'your_exotel_caller_id_here', 'your_exotel_sid_here', 'your_exotel_api_key_here', 'your_exotel_api_token_here'}

if not sid or not api_key or not token or not caller or caller in PLACEHOLDER_VALUES:
    print('STATUS= 400')
    print('TEXT= Exotel credentials are not yet set to real values. Update EXOTEL_SID, EXOTEL_API_KEY, EXOTEL_API_TOKEN and EXOTEL_FROM in .env before testing a live call.')
    raise SystemExit(1)

url = f"https://api.exotel.com/v1/Accounts/{sid}/Calls/connect.json"
payload = {
    'From': caller,
    'To': '+919876543210',
    'CallerId': caller,
    'Url': os.getenv('EXOTEL_TWIML_URL', ''),
}
auth = 'Basic ' + base64.b64encode(f'{api_key}:{token}'.encode()).decode()

print('URL=', url)
print('SID=', sid)
print('CALLER=', caller)
print('TOKEN_PRESENT=', bool(token))
print('TWIML=', payload['Url'])

r = requests.post(url, json=payload, headers={'Authorization': auth, 'Content-Type': 'application/json'}, timeout=60, verify=False)
print('STATUS=', r.status_code)
print('TEXT=', r.text[:1500])
