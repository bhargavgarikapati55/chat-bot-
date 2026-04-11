from flask import Blueprint, request, jsonify, Response, stream_with_context
import json
from app.services.gemini_service import GeminiService
from app.utils.logger import get_logger

logger = get_logger(__name__)

api_bp = Blueprint('api', __name__)

# Initialize single instance of service
gemini_service = None

@api_bp.record_once
def on_load(state):
    global gemini_service
    try:
        gemini_service = GeminiService()
    except Exception as e:
        logger.error(f"Failed to initialize Gemini service: {e}")

@api_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint to verify backend is running."""
    return jsonify({
        "status": "ok", 
        "version": "1.0",
        "service_ready": gemini_service is not None
    }), 200

@api_bp.route('/chat', methods=['POST'])
def chat():
    """Main chat endpoint handling user input and Gemini responses."""
    if not gemini_service:
        return jsonify({"error": "Service Unavailable. API key might be missing."}), 503

    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON payload."}), 400
        
    session_id = data.get('session_id', 'default_session')
    message = data.get('message', '').strip()
    
    if not message:
        return jsonify({"error": "Message cannot be empty."}), 400

    def generate():
        try:
            for text_chunk in gemini_service.send_message_stream(session_id, message):
                # Send SSE data formatted correctly
                yield f"data: {json.dumps({'chunk': text_chunk})}\n\n"
        except Exception as e:
            logger.error(f"Error in chat streaming: {e}")
            yield f"data: {json.dumps({'error': 'An error occurred.'})}\n\n"

    response = Response(stream_with_context(generate()), mimetype='text/event-stream')
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Accel-Buffering'] = 'no'  # Disables buffering for Nginx
    response.headers['Connection'] = 'keep-alive'
    return response
