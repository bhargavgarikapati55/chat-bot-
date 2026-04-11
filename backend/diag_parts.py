import time
from google import genai
from google.genai import types
from app.config import Config
from app.utils.scraper import web_search, scrape_website

client = genai.Client(api_key=Config.GEMINI_API_KEY)
config = types.GenerateContentConfig(
    system_instruction="You are a helpful assistant with web search tools.",
    temperature=0.7,
    tools=[web_search, scrape_website]
)
contents = [types.Content(role="user", parts=[types.Part.from_text(text="What are the latest AI news?")])]
print("Calling API...")
start = time.time()
response = client.models.generate_content_stream(model=Config.GEMINI_MODEL_NAME, contents=contents, config=config)
for chunk in response:
    elapsed = time.time() - start
    if chunk.candidates:
        for part in chunk.candidates[0].content.parts:
            has_text = bool(getattr(part, "text", None))
            has_fc = bool(getattr(part, "function_call", None))
            has_thought = bool(getattr(part, "thought", None))
            print(f"[{elapsed:.1f}s] text={has_text}, function_call={has_fc}, thought={has_thought}")
            if has_text:
                print(f"  TEXT: {part.text[:200]}")
            elif has_fc:
                print(f"  FC: {part.function_call.name}({part.function_call.args})")
            else:
                # Print all attributes of part
                attrs = [a for a in dir(part) if not a.startswith("_")]
                print(f"  ATTRS: {attrs}")
                print(f"  RAW: {repr(part)[:300]}")
    else:
        print(f"[{elapsed:.1f}s] No candidates")
print(f"Done in {time.time()-start:.1f}s")
