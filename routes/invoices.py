from flask import Blueprint, request, jsonify, g
from database import db_required

invoices_bp = Blueprint("invoices", __name__)

@invoices_bp.route("/", methods=["GET"])
@db_required
def get_invoices():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()
    
    query = """
        SELECT i.id, i.patient_id, p.first_name || ' ' || p.last_name AS patient_name,
               i.agreed_price AS amount, i.paid_amount AS paid, i.date, i.status 
        FROM invoices i
        LEFT JOIN patients p ON i.patient_id = p.id
        WHERE 1=1
    """
    params = []
    
    if q:
        query += " AND (p.first_name || ' ' || p.last_name LIKE ?)"
        params.append(f"%{q}%")
        
    if status:
        query += " AND i.status = ?"
        params.append(status)
        
    query += " ORDER BY i.date DESC"
    
    rows = g.db.execute(query, params).fetchall()
    return jsonify([dict(r) for r in rows])

@invoices_bp.route("/", methods=["POST"])
@db_required
def add_invoice():
    d = request.json
    amount = float(d.get('amount', 0))
    paid   = float(d.get('paid', 0))
    agreed = float(d.get('agreed_price', 0))
    payment_method = d.get('payment_method', 'Cash')
    
    # Calculate status automatically
    if paid <= 0: status = "غير مدفوع"
    elif paid < agreed and agreed > 0: status = "جزئي"
    else: status = "مدفوع"

    g.db.execute("INSERT INTO invoices (patient_id, amount, paid, total_amount, paid_amount, agreed_price, payment_method, notes, date, status) VALUES (?,?,?,?,?,?,?,?,?,?)",
                 (d['patient_id'], amount, paid, amount, paid, agreed, payment_method, d.get('notes', ''), d.get('date', ''), status))
    g.db.commit()
    return jsonify({"ok": True})

@invoices_bp.route("/<int:id>/pay", methods=["POST"])
@db_required
def pay_invoice(id):
    d = request.json
    paid_add = float(d.get('amount', 0))
    
    inv = g.db.execute("SELECT total_amount, paid_amount FROM invoices WHERE id = ?", (id,)).fetchone()
    if not inv: return jsonify({"error": "Invoice not found"}), 404
    
    new_paid = inv['paid_amount'] + paid_add
    total = inv['total_amount']
    
    if new_paid <= 0: status = "غير مدفوع"
    elif new_paid < total: status = "جزئي"
    else: status = "مدفوع"
    
    g.db.execute("UPDATE invoices SET paid = ?, paid_amount = ?, status = ? WHERE id = ?", (new_paid, new_paid, status, id))
    g.db.commit()
    return jsonify({"ok": True})
