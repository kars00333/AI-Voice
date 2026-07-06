import asyncio
from dotenv import load_dotenv
load_dotenv()
from google import genai
from google.genai import types

async def main():
    client = genai.Client(http_options={'api_version': 'v1alpha'})
    config = types.LiveConnectConfig(response_modalities=["AUDIO"])
    async with client.aio.live.connect(model='gemini-2.5-flash-native-audio-latest', config=config) as session:
        silence = b'\x00' * 3200
        await session.send(input={"mime_type": "audio/pcm;rate=16000", "data": silence})
        print("Sent audio chunk using session.send(input=...)")
            
asyncio.run(main())
