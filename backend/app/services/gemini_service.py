import os
import json
import time
import http.client
from google import genai
from google.genai import types
from app.config import Config
from app.utils.logger import get_logger
from datetime import datetime
from app.utils.scraper import scrape_website, web_search, google_search

logger = get_logger(__name__)
HEARTBEAT_SIGNAL = "[HEARTBEAT]"


class GeminiService:
    def __init__(self):
        if not Config.GEMINI_API_KEY:
            logger.error("GEMINI_API_KEY is not set.")
            raise ValueError("API key missing.")
        
        # Use a stable model for reliability on free tiers
        self.model_name = Config.GEMINI_MODEL_NAME
        self.client = genai.Client(api_key=Config.GEMINI_API_KEY)
        self.last_api_call_time = 0 # Global timestamp to enforce RPM safety
        self.min_call_interval = 0.5 # Minimum gap between API calls (seconds)
        
        # A dictionary to hold history for sessions
        self.chat_histories = {}
        
        # Mapping tool names to functions for execution
        self.tools_map = {
            "web_search": web_search,
            "google_search": google_search,
            "scrape_website": scrape_website
        }
        
        # Path for memory JSON file
        backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        self.memory_file_path = os.path.join(backend_dir, 'chat_memory.json')
        
        current_date = datetime.now().strftime("%Y-%m-%d")
        self.system_instruction = (
            f"You are a helpful AI assistant with access to web search tools. The current date is {current_date}. "
            f"RULES:\n"
            f"1. For casual conversation, greetings, math, coding, or general knowledge — respond directly WITHOUT using tools.\n"
            f"2. ONLY use tools when the user asks about recent events, news, live data, or something you genuinely need to verify online.\n"
            f"3. FACTUAL ACCURACY IS CRITICAL. Do not rely on your internal knowledge for dates, prices, or recent news. Always verify.\n"
            f"4. If you know an official or high-authority website for a topic (e.g., apple.com for Apple news, wikipedia.org for history), use the 'domain' parameter in 'web_search' or 'google_search' to prioritize it.\n"
            f"5. If a search snippet looks outdated or insufficient, use 'scrape_website' to get the full page content.\n"
            f"6. Cite your sources with URLs. Be concise, helpful, and prioritize official information."
        )

    def _load_memory(self):
        if os.path.exists(self.memory_file_path):
            try:
                with open(self.memory_file_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load memory JSON: {e}")
        return {}

    def _save_memory(self, session_id: str, history: list):
        memory = self._load_memory()
        
        serialized_history = []
        for content in history:
            parts = []
            for part in getattr(content, 'parts', []):
                if getattr(part, 'text', None):
                    parts.append({"text": part.text})
                elif getattr(part, 'function_call', None):
                    parts.append({"function_call": {"name": part.function_call.name, "args": part.function_call.args}})
                elif getattr(part, 'function_response', None):
                    # We store simplified responses for persistence
                    parts.append({"function_response": {"name": part.function_response.name, "response": part.function_response.response}})
            
            serialized_history.append({"role": content.role, "parts": parts})
            
        memory[session_id] = serialized_history
        try:
            with open(self.memory_file_path, 'w') as f:
                json.dump(memory, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save memory JSON: {e}")

    def _get_history(self, session_id: str):
        if session_id not in self.chat_histories:
            memory = self._load_memory()
            session_data = memory.get(session_id, [])
            
            history = []
            for item in session_data:
                parts = []
                for p in item.get("parts", []):
                    if "text" in p:
                        parts.append(types.Part.from_text(text=p["text"]))
                    elif "function_call" in p:
                        fc = p["function_call"]
                        parts.append(types.Part.from_function_call(name=fc["name"], args=fc["args"]))
                    elif "function_response" in p:
                        fr = p["function_response"]
                        parts.append(types.Part.from_function_response(name=fr["name"], response=fr["response"]))
                if parts:
                    history.append(types.Content(role=item.get("role", "user"), parts=parts))
                
            # Prune history to avoid hitting TPM limit
            if len(history) > Config.MAX_HISTORY_MESSAGES:
                logger.info(f"Pruning history for {session_id} to {Config.MAX_HISTORY_MESSAGES} messages.")
                history = history[-Config.MAX_HISTORY_MESSAGES:]
                
            self.chat_histories[session_id] = history
        return self.chat_histories[session_id]

    def _compress_history(self, session_id: str):
        """Replaces large tool results in history with placeholders to save tokens (TPM),
        but PRESERVES the most recent results for accuracy in follow-up turns."""
        if session_id not in self.chat_histories:
            return
            
        history = self.chat_histories[session_id]
        if len(history) <= 3:
            return # Don't compress very short histories
            
        compressed_count = 0
        # Only compress items that are NOT in the last 3 messages
        for content in history[:-3]: 
            if content.role == "tool":
                for part in content.parts:
                    if part.function_response and "result" in part.function_response.response:
                        res = part.function_response.response["result"]
                        if isinstance(res, str) and len(res) > 300:
                            part.function_response.response["result"] = "[Data processed, summarized, and stored in long-term memory]"
                            compressed_count += 1
        
        if compressed_count > 0:
            logger.info(f"Compressed {compressed_count} tool results in history for {session_id}.")
            self._save_memory(session_id, history)

    def _wait_for_global_rate_limit(self):
        """Checks the global rate limit once. Does NOT sleep internally 
        to avoid blocking generators without status updates."""
        elapsed = time.time() - self.last_api_call_time
        if elapsed < self.min_call_interval:
            return self.min_call_interval - elapsed
        return 0

    def _non_blocking_sleep(self, duration: float):
        """Yields heartbeats during sleep to keep the connection alive."""
        start = time.time()
        while time.time() - start < duration:
            yield f"\n\n{HEARTBEAT_SIGNAL}\n\n"
            time.sleep(min(2.0, duration - (time.time() - start)))

    def _api_call_with_retry(self, session_id, contents, stream=False, use_tools=True):
        max_retries = 3
        
        tools = [web_search, google_search, scrape_website] if use_tools else []
        
        config = types.GenerateContentConfig(
            system_instruction=self.system_instruction,
            temperature=0.7,
            tools=tools
        )

        for attempt in range(max_retries):
            try:
                call_start = time.time()
                method = self.client.models.generate_content_stream if stream else self.client.models.generate_content
                result = method(
                    model=self.model_name,
                    contents=contents,
                    config=config
                )
                logger.info(f"API call to {self.model_name} started in {time.time()-call_start:.1f}s")
                return result
            except Exception as e:
                error_msg = str(e)
                
                # Check for 503 (High Demand) or 429 (Quota) to trigger rotation
                if "503" in error_msg or "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                    # SELF-HEALING: Try rotating to a backup model if available
                    backups = getattr(Config, 'GEMINI_BACKUP_MODELS', [])
                    if backups:
                        try:
                            current_idx = backups.index(self.model_name)
                        except ValueError:
                            current_idx = -1
                        
                        next_idx = current_idx + 1
                        if next_idx < len(backups):
                            old_model = self.model_name
                            self.model_name = backups[next_idx]
                            logger.warning(f"Self-Healing: {old_model} failed (Quota/Busy). Rotating to {self.model_name}...")
                            # Return a special signal to caller that we rotated and it should retry immediately
                            raise ValueError(f"ROTATED_TO_{self.model_name}") 
                            
                # If it's a 503 and no rotation possible, still retry after a short sleep
                if "503" in error_msg:
                    logger.warning(f"Gemini 503 (High Demand). Retrying in 2s...")
                    time.sleep(2)
                    continue

                if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                    # PANIC MODE: Turbo-truncation. 
                    if attempt >= 1 and len(contents) > 2:
                        contents[:] = contents[-2:]
                    elif len(contents) > 2: 
                        contents.pop(0)

                    # ADAPTIVE WAIT: Extract server delay but don't sleep here!
                    # Raise it so the caller can yield the status.
                    raise e
                raise e

    def send_message_stream(self, session_id: str, message: str):
        history = self._get_history(session_id)
        
        # Add user message to history
        user_content = types.Content(role="user", parts=[types.Part.from_text(text=message)])
        history.append(user_content)
        
        tool_call_count = 0
        max_tool_calls = Config.MAX_TOOL_CALLS_PER_TURN
        max_turn_retries = 3
        
        while tool_call_count < max_tool_calls:
            turn_success = False
            turn_retry_count = 0
            
            while not turn_success and turn_retry_count < max_turn_retries:
                # If we've failed twice, try 'Safe Mode' (no tools) to save quota
                use_tools = True
                if turn_retry_count >= 2:
                    use_tools = False
                    yield f"\n\n🛡️ *[System: Entering Safe Mode (tools disabled) due to persistent quota limits...]*\n\n"
                
                try:
                    # Enforce global rate limit BEFORE the call
                    wait_time = self._wait_for_global_rate_limit()
                    if wait_time > 0:
                        time.sleep(wait_time)
                    self.last_api_call_time = time.time()
                    
                    # Call the model
                    turn_start = time.time()
                    response = self._api_call_with_retry(session_id, history, stream=True, use_tools=use_tools)
                    
                    # Peek the first chunk
                    try:
                        first_chunk = next(response)
                    except StopIteration:
                        return
                    
                    # Log what we received for debugging
                    if first_chunk.candidates:
                        parts_info = []
                        for p in first_chunk.candidates[0].content.parts:
                            if p.text:
                                parts_info.append(f"text({len(p.text)}chars)")
                            elif p.function_call:
                                parts_info.append(f"function_call({p.function_call.name})")
                            else:
                                parts_info.append("unknown")
                        logger.info(f"First chunk in {time.time()-turn_start:.1f}s: [{', '.join(parts_info)}]")
                    else:
                        logger.warning(f"First chunk in {time.time()-turn_start:.1f}s: NO candidates!")
                    
                    # Check for function calls
                    has_function_call = False
                    if first_chunk.candidates:
                        for part in first_chunk.candidates[0].content.parts:
                            if part.function_call:
                                has_function_call = True
                                break
                    
                    if has_function_call:
                        fc_parts = first_chunk.candidates[0].content.parts
                        history.append(types.Content(role="model", parts=fc_parts))
                        
                        response_parts = []
                        for part in fc_parts:
                            if part.function_call:
                                tool_call_count += 1
                                name = part.function_call.name
                                args = part.function_call.args
                                
                                tool_start = time.time()
                                logger.info(f"Executing tool: {name}({args})")
                                yield f"\n\n🔍 *[Agent: Using {name}...]*\n\n"
                                
                                tool_func = self.tools_map.get(name)
                                if tool_func:
                                    try:
                                        result = tool_func(**args)
                                        logger.info(f"Tool {name} completed in {time.time()-tool_start:.1f}s")
                                        response_parts.append(types.Part.from_function_response(name=name, response={"result": result}))
                                    except Exception as te:
                                        logger.error(f"Tool {name} failed in {time.time()-tool_start:.1f}s: {te}")
                                        response_parts.append(types.Part.from_function_response(name=name, response={"error": str(te)}))
                                else:
                                    response_parts.append(types.Part.from_function_response(name=name, response={"error": f"Tool {name} not found"}))
                        
                        history.append(types.Content(role="tool", parts=response_parts))
                        self.last_api_call_time = time.time()
                        turn_success = True # This turn (tool call) succeeded
                        continue # Outer while loop continues to next tool call iteration
                    else:
                        # Final text response (no function calls)
                        ai_text = ""
                        if first_chunk.candidates:
                            for part in first_chunk.candidates[0].content.parts:
                                if getattr(part, 'text', None):
                                    ai_text += part.text
                                    yield part.text
                        
                        # Continue streaming remaining chunks
                        for chunk in response:
                            if chunk.candidates:
                                for part in chunk.candidates[0].content.parts:
                                    if getattr(part, 'text', None):
                                        ai_text += part.text
                                        yield part.text
                        
                        # Success! Save to history
                        if ai_text:
                            final_parts = [types.Part.from_text(text=ai_text)]
                            history.append(types.Content(role="model", parts=final_parts))
                            self._save_memory(session_id, history)
                            # COMPRESSION: Clean up history after the turn is complete
                            self._compress_history(session_id)
                        turn_success = True
                        return # End of streaming
                        
                except Exception as e:
                    error_msg = str(e)
                    
                    # Check for our rotation signal
                    if error_msg.startswith("ROTATED_TO_"):
                        new_model = error_msg.replace("ROTATED_TO_", "")
                        yield f"\n\n🔄 *[System: Quota reached on primary model. Switching to {new_model}...]*\n\n"
                        # We don't increment retry count for a rotation
                        continue

                    # Handle Rate Limits, High Demand, and Connection Drops
                    if any(err in error_msg for err in ["429", "RESOURCE_EXHAUSTED", "503", "RemoteDisconnected", "Connection aborted", "Remote end closed connection"]):
                        turn_retry_count += 1
                        wait_time = 15 * turn_retry_count # Reduced initial wait
                        yield f"\n\n⏳ *[System: Server busy or Quota hit. Re-syncing in {wait_time}s...]*\n\n"
                        logger.warning(f"Transient error in stream: {error_msg}. Waiting {wait_time}s to retry turn.")
                        for hb in self._non_blocking_sleep(wait_time):
                            yield hb
                        continue
                    else:
                        logger.error(f"Fatal error in stream: {e}")
                        yield f"\n[Error: {error_msg}]"
                        return

            if not turn_success:
                yield "\n\n⚠️ **Quota Limit Reached**: The Gemini Free Tier limit was reached. Please wait a minute before trying again, or try a shorter prompt."
                return

        if tool_call_count >= max_tool_calls:
            yield "\n\n⚠️ **Agent Limit**: Maximum tool browsing depth reached. Stopping here to save quota."

    def send_message(self, session_id: str, message: str) -> str:
        # Fallback to streaming implementation for consistency
        full_text = ""
        for chunk in self.send_message_stream(session_id, message):
            if not chunk.startswith("\n\n🔍") and not chunk.startswith("\n\n⚠️"):
                full_text += chunk
        return full_text
