import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FOLDER = os.path.abspath(os.path.join(BASE_DIR, "..", "databases"))

def migrate():
    db_path = os.path.join(BASE_DIR, "clinic.db")
    if not os.path.exists(db_path):
        print("clinic.db not found")
        return
        
    print(f"Migrating {db_path}...")
    conn = sqlite3.connect(db_path)
    
    # Patient Table Migrations
    patient_cols = [
        ("occupation", "TEXT"),
        ("age", "INTEGER"),
        ("systemic_conditions", "TEXT"),
        ("case_category", "TEXT"),
        ("is_ongoing", "INTEGER DEFAULT 1"),
        ("case_notes", "TEXT"),
        ("case_images", "TEXT"),
        ("case_doctor", "TEXT"),
        ("quad_ur", "TEXT"),
        ("quad_ul", "TEXT"),
        ("quad_lr", "TEXT"),
        ("quad_ll", "TEXT"),
        ("status", "TEXT DEFAULT 'جديد'")
    ]
    for col, type in patient_cols:
        try:
            conn.execute(f"ALTER TABLE patients ADD COLUMN {col} {type}")
            print(f"Added {col} to patients")
        except sqlite3.OperationalError: pass

    # Invoices Table Migrations
    invoice_cols = [
        ("agreed_price", "REAL DEFAULT 0"),
        ("notes", "TEXT"),
        ("total_amount", "REAL DEFAULT 0"),
        ("paid_amount", "REAL DEFAULT 0"),
        ("payment_method", "TEXT DEFAULT 'Cash'"),
        ("status", "TEXT DEFAULT 'مدفوع'")
    ]
    for col, type in invoice_cols:
        try:
            conn.execute(f"ALTER TABLE invoices ADD COLUMN {col} {type}")
            print(f"Added {col} to invoices")
        except sqlite3.OperationalError: pass

    try:
        conn.execute("ALTER TABLE expenses ADD COLUMN payment_method TEXT DEFAULT 'Cash'")
        print("Added payment_method to expenses")
    except sqlite3.OperationalError: pass
        
    conn.commit()
    conn.close()
    print("Migration complete!")

if __name__ == "__main__":
    migrate()
