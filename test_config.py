from dotenv import load_dotenv
load_dotenv()
from google.genai import types

print("=== LiveConnectConfig fields ===")
for f in types.LiveConnectConfig.model_fields:
    print(f"  {f}: {types.LiveConnectConfig.model_fields[f].annotation}")

print("\n=== RealtimeInputConfig ===")
for f in types.RealtimeInputConfig.model_fields:
    print(f"  {f}: {types.RealtimeInputConfig.model_fields[f].annotation}")

print("\n=== AutomaticActivityDetection ===")
for f in types.AutomaticActivityDetection.model_fields:
    print(f"  {f}: {types.AutomaticActivityDetection.model_fields[f].annotation}")
