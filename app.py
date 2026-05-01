import os
from flask import Flask, send_from_directory, jsonify, g, request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from database import init_db

from routes.patients import patients_bp
from routes.appointments import appointments_bp
from routes.invoices import invoices_bp
from routes.settings import settings_bp
from routes.expenses import expenses_bp
from routes.auth import auth_bp
from routes.stats import stats_bp

from extensions import limiter

app = Flask(__name__, static_folder="static")
app.config["SECRET_KEY"] = "smile-care-super-secret-key-2026"

# Initialize Extensions
limiter.init_app(app)

CORS(app, resources={r"/api/*": {
    "origins": ["http://localhost:3000", "https://your-netlify-app.netlify.app"],
    "allow_headers": ["Content-Type", "Authorization", "X-Username"]
}})

# Global Error Handler (Issue #11)
@app.errorhandler(Exception)
def handle_exception(e):
    # Log the error internally (Issue #9)
    app.logger.error(f"Server Error: {str(e)}")
    # Return a clean JSON response instead of a stack trace
    return jsonify({
        "error": "An internal server error occurred. Please try again later.",
        "details": str(e) if app.debug else None
    }), 500



# Ensure uploads directory exists
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "static", "uploads")
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

app.register_blueprint(patients_bp,     url_prefix="/api/patients")
app.register_blueprint(appointments_bp, url_prefix="/api/appointments")
app.register_blueprint(invoices_bp,     url_prefix="/api/invoices")
app.register_blueprint(settings_bp,     url_prefix="/api/settings")
app.register_blueprint(expenses_bp,     url_prefix="/api/expenses")
app.register_blueprint(auth_bp,         url_prefix="/api/auth")
app.register_blueprint(stats_bp,        url_prefix="/api/stats")

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    if path != "" and os.path.exists(app.static_folder + '/' + path):
        return send_from_directory(app.static_folder, path)
    else:
        return send_from_directory(app.static_folder, 'index.html')

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5050, debug=True)
