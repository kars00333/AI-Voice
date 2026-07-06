import asyncio
from dotenv import load_dotenv
load_dotenv()
from google import genai
from google.genai import types
import inspect

async def main():
    client = genai.Client(http_options={'api_version': 'v1alpha'})
    
    # Check available config fields for VAD/input settings
    sig = inspect.signature(types.LiveConnectConfig.__init__)
    print("LiveConnectConfig fields related to input/VAD/activity:")
    for name, param in sig.parameters.items():
        if name == 'self':
            continue
        print(f"  {name}")
    
    # Check if there's a RealtimeInputConfig type
    for attr in dir(types):
        if 'realtime' in attr.lower() or 'activity' in attr.lower() or 'vad' in attr.lower():
            print(f"\ntypes.{attr}")

asyncio.run(main())
