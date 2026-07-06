import asyncio
from dotenv import load_dotenv
load_dotenv()
from google import genai
from google.genai import types

async def main():
    client = genai.Client(http_options={'api_version': 'v1alpha'})
    config = types.LiveConnectConfig(response_modalities=["AUDIO"])
    async with client.aio.live.connect(model='gemini-2.5-flash-native-audio-latest', config=config) as session:
        await session.send(input="Hello, can you hear me? Say something back.", end_of_turn=True)
        async for message in session.receive():
            if message.server_content and message.server_content.model_turn:
                for part in message.server_content.model_turn.parts:
                    print(f"Received part: text={bool(part.text)}, inline_data={bool(part.inline_data)}")
            if message.server_content and message.server_content.turn_complete:
                print("Turn complete")
                break

asyncio.run(main())
