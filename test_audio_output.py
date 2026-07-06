import asyncio
from dotenv import load_dotenv
load_dotenv()
from google import genai
from google.genai import types

async def main():
    client = genai.Client(http_options={'api_version': 'v1alpha'})
    
    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Aoede")
            )
        ),
    )
    
    print(f"genai version: {genai.__version__}")
    
    async with client.aio.live.connect(model='gemini-2.5-flash-native-audio-latest', config=config) as session:
        await session.send_client_content(
            turns=types.Content(
                role="user",
                parts=[types.Part(text="Say hello, how are you today?")]
            ),
            turn_complete=True,
        )
        
        audio_bytes_total = 0
        text_total = ""
        msg_count = 0
        
        async for msg in session.receive():
            msg_count += 1
            if msg.server_content:
                mt = msg.server_content.model_turn
                if mt:
                    for part in mt.parts:
                        if part.inline_data:
                            audio_bytes_total += len(part.inline_data.data)
                            print(f"  msg#{msg_count}: AUDIO chunk {len(part.inline_data.data)} bytes, mime={part.inline_data.mime_type}")
                        if part.text:
                            text_total += part.text
                            print(f"  msg#{msg_count}: TEXT: {part.text[:100]}")
                if msg.server_content.turn_complete:
                    print(f"\n--- Turn complete ---")
                    print(f"Total audio: {audio_bytes_total} bytes")
                    print(f"Total text: {len(text_total)} chars: {text_total[:200]}")
                    break

asyncio.run(main())
