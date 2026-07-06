import asyncio
from dotenv import load_dotenv
load_dotenv()
from google import genai
from google.genai import types

async def main():
    client = genai.Client(http_options={'api_version': 'v1alpha'})
    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=types.Content(parts=[types.Part.from_text(text="Hi")]),
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                    voice_name="Aoede"
                )
            )
        )
    )
    try:
        async with client.aio.live.connect(model='gemini-2.5-flash-native-audio-latest', config=config) as session:
            await session.send(input="Hello", end_of_turn=True)
            async for message in session.receive():
                print("Received message")
                break
    except Exception as e:
        print(f"Exception: {e}")

asyncio.run(main())
