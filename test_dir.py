import asyncio
from dotenv import load_dotenv
load_dotenv()
from google import genai
from google.genai import types

async def main():
    client = genai.Client(http_options={'api_version': 'v1alpha'})
    config = types.LiveConnectConfig(response_modalities=["AUDIO"])
    async with client.aio.live.connect(model='gemini-2.5-flash-native-audio-latest', config=config) as session:
        import inspect
        print("send_realtime_input signature:", inspect.signature(session.send_realtime_input))
            
asyncio.run(main())
