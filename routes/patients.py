import json
import os
import uuid
import datetime
from flask import Blueprint, request, jsonify, g
from database import db_required

patients_bp = Blueprint("patients", __name__)

@patients_bp.route("/prescriptions/all", methods=["GET"])
@db_required
def get_all_prescriptions():
    query = """
        SELECT pr.*, p.first_name || ' ' || p.last_name AS patient_name
        FROM prescriptions pr
        JOIN patients p ON pr.patient_id = p.id
        ORDER BY pr.date DESC
    """
    rows = g.db.execute(query).fetchall()
    return jsonify([dict(r) for r in rows])

@patients_bp.route("/", methods=["GET"])
@db_required
def get_patients():
    q = request.args.get("q", "")
    status = request.args.get("status", "")
    page = int(request.args.get("page", 1))
    limit = int(request.args.get("limit", 50))
    offset = (page - 1) * limit
    
    query = """
        SELECT p.*, MAX(a.date) as last_visit 
        FROM patients p
        LEFT JOIN appointments a ON p.id = a.patient_id
        WHERE (p.first_name LIKE ? OR p.last_name LIKE ? OR p.phone LIKE ?)
    """
    params = [f"%{q}%", f"%{q}%", f"%{q}%"]
    
    if status:
        query += " AND p.status = ?"
        params.append(status)
        
    query += " GROUP BY p.id ORDER BY p.id DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    rows = g.db.execute(query, params).fetchall()
    return jsonify([dict(r) for r in rows])

@patients_bp.route("/<int:id>", methods=["PUT"])
@db_required
def update_patient(id):
    d = request.json
    fields = [
        'first_name', 'last_name', 'phone', 'birth_date', 'age', 'gender', 
        'occupation', 'address', 'systemic_conditions', 'notes', 
        'case_category', 'is_ongoing', 'status', 'case_notes', 'case_images'
    ]
    
    # Map arrays to strings if they exist
    if 'case_notes' in d and isinstance(d['case_notes'], (list, dict)):
        d['case_notes'] = json.dumps(d['case_notes'])
    if 'case_images' in d and isinstance(d['case_images'], (list, dict)):
        d['case_images'] = json.dumps(d['case_images'])

    set_clause = ", ".join([f"{f} = ?" for f in fields if f in d])
    values = [d[f] for f in fields if f in d]
    values.append(id)
    
    if set_clause:
        sql = f"UPDATE patients SET {set_clause} WHERE id = ?"
        g.db.execute(sql, values)
        
    if 'agreed_price' in d:
        # Check if an invoice exists for this patient
        inv = g.db.execute("SELECT id FROM invoices WHERE patient_id = ?", (id,)).fetchone()
        if inv:
            g.db.execute("UPDATE invoices SET agreed_price = ? WHERE patient_id = ?", (d['agreed_price'], id))
        else:
            # Create a default invoice with the agreed price
            g.db.execute("INSERT INTO invoices (patient_id, agreed_price, status, date) VALUES (?, ?, ?, CURRENT_DATE)", 
                         (id, d['agreed_price'], 'غير مدفوع'))

    g.db.commit()
    return jsonify({"ok": True})

@patients_bp.route("/", methods=["POST"])
@db_required
def add_patient():
    d = request.json
    fields = [
        'first_name', 'last_name', 'phone', 'birth_date', 'age', 'gender', 
        'occupation', 'address', 'systemic_conditions', 'notes', 
        'case_category', 'is_ongoing', 'status'
    ]
    
    # Use default values if missing
    values = [d.get(f, "") for f in fields]
    if not d.get('status'): values[fields.index('status')] = 'جديد'

    placeholders = ", ".join(["?"] * len(fields))
    col_names = ", ".join(fields)
    
    sql = f"INSERT INTO patients ({col_names}) VALUES ({placeholders})"
    cur = g.db.execute(sql, values)
    g.db.commit()
    return jsonify({"id": cur.lastrowid})

import json

@patients_bp.route("/<int:id>", methods=["GET"])
@db_required
def get_patient(id):
    p = g.db.execute("SELECT * FROM patients WHERE id=?", (id,)).fetchone()
    if not p: return jsonify({"error": "NotFound"}), 404
    res = dict(p)
    
    # Get last 10 appointments
    res['visits'] = [dict(r) for r in g.db.execute("SELECT * FROM appointments WHERE patient_id=? ORDER BY date DESC LIMIT 10", (id,)).fetchall()]
    
    # Get invoices with aliases
    inv_query = "SELECT id, agreed_price, total_amount AS amount, paid_amount AS paid, date, status FROM invoices WHERE patient_id=? ORDER BY date DESC"
    res['invoices'] = [dict(r) for r in g.db.execute(inv_query, (id,)).fetchall()]
    
    # Get prescriptions
    res['prescriptions'] = [dict(r) for r in g.db.execute("SELECT * FROM prescriptions WHERE patient_id=? ORDER BY date DESC", (id,)).fetchall()]
    
    def safe_json(s):
        try:
            return json.loads(s) if s else []
        except:
            return []

    tm = g.db.execute("SELECT map_data FROM teeth_map WHERE patient_id=?", (id,)).fetchone()
    res['teeth'] = safe_json(tm['map_data']) if tm else []
    res['case_notes'] = safe_json(res.get('case_notes'))
    res['case_images'] = safe_json(res.get('case_images'))
    
    return jsonify(res)

@patients_bp.route("/<int:id>/teeth", methods=["POST"])
@db_required
def update_teeth(id):
    data = json.dumps(request.json)
    g.db.execute("INSERT OR REPLACE INTO teeth_map (patient_id, map_data) VALUES (?, ?)", (id, data))
    g.db.commit()
    return jsonify({"ok": True})

import os
import uuid
import datetime

@patients_bp.route("/<int:id>/prescriptions", methods=["POST"])
@db_required
def add_prescription(id):
    # Support both JSON and multipart/form-data
    if request.is_json:
        d = request.json
        image_url = d.get('image_url', '')
        date = d.get('date', datetime.date.today().isoformat())
        meds = d.get('meds', '')
        notes = d.get('notes', '')
    else:
        # File upload
        date = request.form.get('date', datetime.date.today().isoformat())
        meds = request.form.get('meds', '')
        notes = request.form.get('notes', '')
        image_url = ''
        
        if 'image' in request.files:
            file = request.files['image']
            if file.filename != '':
                ext = file.filename.rsplit('.', 1)[1].lower()
                filename = f"presc_{id}_{uuid.uuid4().hex}.{ext}"
                upload_path = os.path.join(os.path.dirname(__file__), "..", "static", "uploads", filename)
                file.save(upload_path)
                image_url = f"/uploads/{filename}"

    g.db.execute("INSERT INTO prescriptions (patient_id, meds, notes, date, image_url) VALUES (?, ?, ?, ?, ?)",
                 (id, meds, notes, date, image_url))
    g.db.commit()
    return jsonify({"ok": True, "image_url": image_url})

@patients_bp.route("/prescriptions/<int:presc_id>", methods=["DELETE"])
@db_required
def delete_prescription(presc_id):
    g.db.execute("DELETE FROM prescriptions WHERE id = ?", (presc_id,))
    g.db.commit()
    return jsonify({"ok": True})

@patients_bp.route("/prescriptions/<int:presc_id>", methods=["PUT"])
@db_required
def update_prescription(presc_id):
    d = request.json
    g.db.execute("UPDATE prescriptions SET meds = ?, notes = ?, date = ? WHERE id = ?",
                 (d.get('meds', ''), d.get('notes', ''), d.get('date', ''), presc_id))
    g.db.commit()
    return jsonify({"ok": True})
