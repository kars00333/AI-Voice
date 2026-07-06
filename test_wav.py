import asyncio
import wave
from dotenv import load_dotenv
load_dotenv()
from google import genai
from google.genai import types

async def main():
    client = genai.Client(http_options={'api_version': 'v1alpha'})
    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=types.Content(parts=[types.Part.from_text(text="You are a helpful assistant. Reply to the user.")])
    )
    async with client.aio.live.connect(model='gemini-2.5-flash-native-audio-latest', config=config) as session:
        # We need a 16kHz wav file. Let's just generate a 1-second 440Hz sine wave as a test, or wait...
        # A sine wave might not trigger VAD. Let's just say "Hello" as text to verify VAD is even the problem.
        # Oh wait, we want to test audio.
        pass
