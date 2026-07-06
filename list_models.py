import os
from dotenv import load_dotenv
load_dotenv()
from google import genai
client = genai.Client(http_options={'api_version': 'v1alpha'})
for m in client.models.list():
    if 'gemini-2' in m.name:
        print(m.name, m.supported_actions)
