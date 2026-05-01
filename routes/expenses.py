from flask import Blueprint, request, jsonify, g
from database import db_required

expenses_bp = Blueprint("expenses", __name__)

@expenses_bp.route("/", methods=["GET"])
@db_required
def get_expenses():
    rows = g.db.execute("SELECT * FROM expenses").fetchall()
    return jsonify([dict(r) for r in rows])

@expenses_bp.route("/", methods=["POST"])
@db_required
def add_expense():
    d = request.json
    g.db.execute("INSERT INTO expenses (category, amount, payment_method, date, notes) VALUES (?,?,?,?,?)",
                 (d['category'], d['amount'], d.get('payment_method', 'Cash'), d['date'], d.get('notes')))
    g.db.commit()
    return jsonify({"ok": True})

@expenses_bp.route("/<int:id>", methods=["DELETE"])
@db_required
def delete_expense(id):
    g.db.execute("DELETE FROM expenses WHERE id = ?", (id,))
    g.db.commit()
    return jsonify({"ok": True})
