import os
from datetime import timedelta
from pathlib import Path

from flask_cors import CORS
from flask import Flask, send_from_directory
from dotenv import load_dotenv

from database import init_db
from routes.item_routes import item_bp
from routes.auth_routes import auth_bp
from routes.match_routes import match_bp
from routes.upload_routes import upload_bp
from routes.claim_routes import claim_bp

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

app = Flask(__name__)

CORS(
    app,
    resources={
        r"/*": {
            "origins": [
                "http://127.0.0.1:5500",
                "http://localhost:5500",
                "http://127.0.0.1:5501",
                "http://localhost:5501",
                "http://127.0.0.1:5000",
                "http://localhost:5000",
                "http://127.0.0.1:3000",
                "http://localhost:3000"
            ]
        }
    },
    supports_credentials=True
)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY")

if not app.config["SECRET_KEY"]:
    raise RuntimeError("SECRET_KEY is required")

app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = (
    os.environ.get("COOKIE_SECURE", "false").lower() == "true"
)

app.permanent_session_lifetime = timedelta(hours=2)

# Upload configuration
UPLOAD_FOLDER = BASE_DIR / "uploads"
UPLOAD_FOLDER.mkdir(exist_ok=True)

app.config["UPLOAD_FOLDER"] = str(UPLOAD_FOLDER)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

# Initialize database
init_db()

# Serve uploaded images
@app.route("/uploads/<path:filename>")
def serve_upload(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

# Register API routes
app.register_blueprint(item_bp, url_prefix="/api/items")
app.register_blueprint(auth_bp, url_prefix="/api/auth")
app.register_blueprint(match_bp, url_prefix="/api/matches")
app.register_blueprint(upload_bp, url_prefix="/api/uploads")
app.register_blueprint(claim_bp, url_prefix="/api/claims")

if __name__ == "__main__":
    app.run(debug=True)
