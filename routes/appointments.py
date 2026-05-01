from flask import Blueprint, request, jsonify, g
from database import db_required

appointments_bp = Blueprint("appointments", __name__)

@appointments_bp.route("/", methods=["GET"])
@db_required
def get_appointments():
    pid = request.args.get("pid")
    date = request.args.get("date") # Optional filter for Home.jsx
    
    query = """
        SELECT a.*, p.first_name || ' ' || p.last_name AS patient_name 
        FROM appointments a
        JOIN patients p ON a.patient_id = p.id
    """
    params = []
    
    if pid:
        query += " WHERE a.patient_id = ?"
        params.append(pid)
    elif date:
        query += " WHERE a.date = ?"
        params.append(date)
        
    query += " ORDER BY a.date DESC, a.time DESC"
    rows = g.db.execute(query, params).fetchall()
    return jsonify([dict(r) for r in rows])

@appointments_bp.route("/", methods=["POST"])
@db_required
def add_appointment():
    d = request.json
    g.db.execute(
        "INSERT INTO appointments (patient_id, date, time, type, duration_min, status, notes) VALUES (?,?,?,?,?,?,?)",
        (d['patient_id'], d['date'], d['time'], 
         d.get('type', d.get('treatment', '')),
         d.get('duration_min', d.get('duration', 30)),
         d.get('status', 'قادم'),
         d.get('notes', ''))
    )
    g.db.commit()
    return jsonify({"ok": True})

@appointments_bp.route("/<int:id>", methods=["DELETE"])
@db_required
def delete_appointment(id):
    g.db.execute("DELETE FROM appointments WHERE id = ?", (id,))
    g.db.commit()
    return jsonify({"ok": True})
