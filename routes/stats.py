from flask import Blueprint, request, jsonify, g
from database import db_required
from datetime import datetime

stats_bp = Blueprint("stats", __name__)

@stats_bp.route("/summary", methods=["GET"])
@db_required
def get_summary():
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Appointments today
    total_today = g.db.execute("SELECT COUNT(*) FROM appointments WHERE date = ?", (today,)).fetchone()[0]
    
    # Total Patients
    total_patients = g.db.execute("SELECT COUNT(*) FROM patients").fetchone()[0]
    
    # Debt Calculation: sum of (max agreed_price - sum paid_amount) per patient
    debt_query = """
        SELECT SUM(debt) FROM (
            SELECT MAX(agreed_price) - SUM(paid_amount) as debt
            FROM invoices
            GROUP BY patient_id
            HAVING debt > 0
        )
    """
    debt_total = g.db.execute(debt_query).fetchone()[0] or 0
    
    # Debt Count
    debt_count_query = """
        SELECT COUNT(*) FROM (
            SELECT patient_id
            FROM invoices
            GROUP BY patient_id
            HAVING MAX(agreed_price) - SUM(paid_amount) > 0
        )
    """
    debt_count = g.db.execute(debt_count_query).fetchone()[0]
    
    return jsonify({
        "total_today": total_today,
        "debt_total": debt_total,
        "total_patients": total_patients,
        "debt_count": debt_count
    })

@stats_bp.route("/financial", methods=["GET"])
@db_required
def get_financial():
    today = datetime.now().strftime("%Y-%m-%d")
    month = datetime.now().strftime("%Y-%m")
    
    # Revenue (Collected) — use local date
    collected_today = g.db.execute(
        "SELECT SUM(paid_amount) FROM invoices WHERE date = ? AND paid_amount > 0", 
        (today,)
    ).fetchone()[0] or 0
    collected_month = g.db.execute(
        "SELECT SUM(paid_amount) FROM invoices WHERE date LIKE ? AND paid_amount > 0", 
        (f"{month}%",)
    ).fetchone()[0] or 0
    total_revenue = g.db.execute("SELECT SUM(paid_amount) FROM invoices").fetchone()[0] or 0
    
    # Expenses
    total_expenses = g.db.execute("SELECT SUM(amount) FROM expenses").fetchone()[0] or 0
    expenses_today = g.db.execute("SELECT SUM(amount) FROM expenses WHERE date = ?", (today,)).fetchone()[0] or 0
    
    # Cash vs Bank (Collected Revenue)
    cash_collected = g.db.execute("SELECT SUM(paid_amount) FROM invoices WHERE payment_method = 'Cash'").fetchone()[0] or 0
    bank_collected = g.db.execute("SELECT SUM(paid_amount) FROM invoices WHERE payment_method = 'Bank'").fetchone()[0] or 0
    
    cash_expenses = g.db.execute("SELECT SUM(amount) FROM expenses WHERE payment_method = 'Cash'").fetchone()[0] or 0
    bank_expenses = g.db.execute("SELECT SUM(amount) FROM expenses WHERE payment_method = 'Bank'").fetchone()[0] or 0
    
    cash_balance = cash_collected - cash_expenses
    bank_balance = bank_collected - bank_expenses
    
    # Debt logic
    agreed_total = g.db.execute("SELECT SUM(agreed) FROM (SELECT MAX(agreed_price) as agreed FROM invoices GROUP BY patient_id)").fetchone()[0] or 0
    total_debt = agreed_total - total_revenue
    
    # Collection Rate
    collection_rate = (total_revenue / agreed_total * 100) if agreed_total > 0 else 100

    return jsonify({
        "collected_today": collected_today,
        "collected_month": collected_month,
        "expenses_today": expenses_today,
        "revenue": total_revenue,
        "expenses": total_expenses,
        "net_profit": total_revenue - total_expenses,
        "total_debt": total_debt,
        "cash_revenue": cash_balance,
        "bank_revenue": bank_balance,
        "collection_rate": round(collection_rate, 1)
    })

@stats_bp.route("/debts", methods=["GET"])
@db_required
def get_debts():
    query = """
        SELECT p.id, p.first_name, p.last_name, p.phone,
               MAX(i.agreed_price) as total_amt,
               SUM(i.paid_amount) as total_paid,
               MAX(i.agreed_price) - SUM(i.paid_amount) as debt
        FROM patients p
        JOIN invoices i ON p.id = i.patient_id
        GROUP BY p.id
        HAVING debt > 0
        ORDER BY debt DESC
    """
    rows = g.db.execute(query).fetchall()
    return jsonify([dict(r) for r in rows])

@stats_bp.route("/invoices/summary", methods=["GET"])
@db_required
def get_invoice_summary():
    # Calculate sum of agreed_price per patient
    today = datetime.now().strftime("%Y-%m-%d")
    agreed_total = g.db.execute("SELECT SUM(agreed) FROM (SELECT MAX(agreed_price) as agreed FROM invoices GROUP BY patient_id)").fetchone()[0] or 0
    total_collected = g.db.execute("SELECT SUM(paid_amount) FROM invoices").fetchone()[0] or 0
    
    today_total = g.db.execute("SELECT SUM(agreed_price) FROM invoices WHERE date = ?", (today,)).fetchone()[0] or 0
    today_collected = g.db.execute("SELECT SUM(paid_amount) FROM invoices WHERE date = ?", (today,)).fetchone()[0] or 0

    return jsonify({
        "total": agreed_total,
        "collected": total_collected,
        "debt": agreed_total - total_collected,
        "today_total": today_total,
        "today_collected": today_collected
    })
