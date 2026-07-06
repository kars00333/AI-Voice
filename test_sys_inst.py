import asyncio
from dotenv import load_dotenv
load_dotenv()
from google import genai
from google.genai import types

async def main():
    client = genai.Client(http_options={'api_version': 'v1alpha'})
    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=types.Content(parts=[types.Part.from_text(text="You are a funny bot. START THE CALL by saying: 'Hi, I need to make an appointment'")])
    )
    async with client.aio.live.connect(model='gemini-2.5-flash-native-audio-latest', config=config) as session:
        await session.send(input="Hello", end_of_turn=True)
        async for message in session.receive():
            if message.server_content and message.server_content.model_turn:
                for part in message.server_content.model_turn.parts:
                    print(f"Received part: text={bool(part.text)}, inline_data={bool(part.inline_data)}")
            if message.server_content and message.server_content.turn_complete:
                print("Turn complete")
                break

asyncio.run(main())
