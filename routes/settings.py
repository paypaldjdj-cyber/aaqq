from flask import Blueprint, request, jsonify, g
from database import db_required

settings_bp = Blueprint("settings", __name__)

@settings_bp.route("/reset", methods=["POST"])
@db_required
def reset_clinic():
    # Reset wipes all clinical data
    tables = ["patients", "appointments", "invoices", "expenses", "teeth_map", "prescriptions"]
    for t in tables: g.db.execute(f"DELETE FROM {t}")
    g.db.commit()
    return jsonify({"ok": True})

@settings_bp.route("/", methods=["GET", "PUT"])
@db_required
def manage_settings():
    if request.method == "PUT":
        d = request.json
        for k, v in d.items():
            g.db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (k, v))
        g.db.commit()
        return jsonify({"ok": True})
    rows = g.db.execute("SELECT * FROM settings").fetchall()
    return jsonify({r['key']: r['value'] for r in rows})

from flask import send_file
import os

@settings_bp.route("/backup", methods=["GET"])
@db_required
def backup_db():
    db_path = os.path.join(os.getcwd(), "clinic.db")
    return send_file(db_path, as_attachment=True)
