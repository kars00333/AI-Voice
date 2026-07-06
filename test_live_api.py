import asyncio
from google import genai

async def main():
    try:
        client = genai.Client(http_options={'api_version': 'v1alpha'})
        async with client.aio.live.connect(model='gemini-2.0-flash-exp') as session:
            print("Connected successfully!")
            await session.send(input="hello")
    except Exception as e:
        print(f"Error: {e}")

asyncio.run(main())
