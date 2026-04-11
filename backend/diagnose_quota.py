import os
import time
from google import genai
from dotenv import load_dotenv

load_dotenv('.env')
api_key = os.getenv('GEMINI_API_KEY')
client = genai.Client(api_key=api_key)

print(f"--- Gemini AI Quota Diagnostic ---")
print(f"API Key: {api_key[:10]}...{api_key[-5:]}")

try:
    models = [m.name for m in client.models.list() if 'flash' in m.name or 'pro' in m.name]
    print(f"Found {len(models)} candidate models.")
except Exception as e:
    print(f"Error listing models: {e}")
    models = ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-2.0-flash-lite"]

results = []

for model_path in models:
    model_name = model_path.replace('models/', '')
    print(f"\nTesting {model_name}...", end=" ", flush=True)
    
    start_time = time.time()
    try:
        response = client.models.generate_content(
            model=model_name,
            contents="Say 'OK'"
        )
        duration = time.time() - start_time
        print(f"SUCCESS ({duration:.2f}s)")
        results.append((model_name, "SUCCESS", duration))
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
            print("FAILED (Quota Exhausted)")
            results.append((model_name, "429", error_msg))
        elif "404" in error_msg:
            print("FAILED (Not Found)")
            results.append((model_name, "404", error_msg))
        else:
            print(f"FAILED (Other: {error_msg[:50]}...)")
            results.append((model_name, "ERROR", error_msg))
    
    time.sleep(2) # Small gap between tests

print("\n--- Summary ---")
for res in results:
    print(f"{res[0]:<30} | {res[1]}")

active_models = [r[0] for r in results if r[1] == "SUCCESS"]
if active_models:
    print(f"\nRECCOMENDED MODEL: {active_models[0]}")
else:
    print("\nCRITICAL: No models responded successfully. This suggests a project-level block or billing issue.")
