import os
from flask import Flask, send_from_directory
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from app.config import Config

# Initialize rate limiter using remote address as key
limiter = Limiter(key_func=get_remote_address, default_limits=[Config.RATE_LIMIT_DEFAULT])

def create_app():
    # Setup App to point static folders to the parent directory (frontend)
    # The parent directory of the backend folder is the chatgpt-clone folder
    frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    
    app = Flask(__name__, static_folder=frontend_dir, static_url_path='')
    app.config.from_object(Config)

    # Enable CORS for frontend interactions
    CORS(app)
    
    # Initialize Limiter
    limiter.init_app(app)

    # Register API blueprints
    from app.routes import api_bp
    app.register_blueprint(api_bp, url_prefix='/api')

    # Serve Frontend Pages
    @app.route('/')
    def index():
        return app.send_static_file('index.html')

    @app.route('/favicon.ico')
    def favicon():
        return '', 204 # No Content, but prevents 404

    return app
