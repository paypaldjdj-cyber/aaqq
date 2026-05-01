import sqlite3
import os
import jwt
from flask import request, g, jsonify, current_app
from functools import wraps

# Get the absolute path to the directory where database.py is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# The databases folder should be in the parent directory (root)
DB_FOLDER = os.path.abspath(os.path.join(BASE_DIR, "..", "databases"))

if not os.path.exists(DB_FOLDER):
    os.makedirs(DB_FOLDER)

# Database path
MASTER_DB_PATH = os.path.join(DB_FOLDER, "master.db")

def get_master_db():
    conn = sqlite3.connect(MASTER_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_db(username=None):
    if not username:
        token = request.headers.get("Authorization")
        username = "default"
        if token:
            try:
                if " " in token: token = token.split(" ")[1]
                data = jwt.decode(token, "smile-care-super-secret-key-2026", algorithms=["HS256"])
                username = data.get("username")
                g.user = data
            except:
                pass

    db_name = f"clinic_{username}.db"
    db_path = os.path.join(DB_FOLDER, db_name)
    print(f"--- Secure Access: {db_name} ---")
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    init_clinic_schema(conn)
    return conn

def init_db():
    conn = get_master_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS doctors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            clinic_name TEXT,
            doctor_name TEXT,
            expiry_date TEXT,
            status TEXT DEFAULT 'active',
            secretary_enabled INTEGER DEFAULT 0,
            secretary_password TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_doctors_username ON doctors(username)")
    
    # Master Settings Table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS master_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    conn.execute("INSERT OR IGNORE INTO master_settings (key, value) VALUES ('support_phone', '07XXXXXXXXX')")
    
    # Migrations for master.db
    columns = [
        ("expiry_date", "TEXT"), 
        ("status", "TEXT DEFAULT 'active'"), 
        ("secretary_enabled", "INTEGER DEFAULT 0"), 
        ("secretary_password", "TEXT"),
        ("doctor_name", "TEXT"),
        ("clinic_name", "TEXT")
    ]
    for col, ctype in columns:
        try: conn.execute(f"ALTER TABLE doctors ADD COLUMN {col} {ctype}")
        except: pass
        
    # Create an initial superadmin if needed or default doctor
    conn.execute("INSERT OR IGNORE INTO doctors (username, password, clinic_name, status) VALUES ('doctor', 'doctor123', 'عيادة الابتسامة', 'active')")
    conn.commit()
    conn.close()

    # Also init default db just in case
    conn = get_db("doctor")
    init_clinic_schema(conn)
    conn.close()

def init_clinic_schema(conn):
    # Standard Clinic Tables
    conn.execute("""
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT,
            last_name TEXT,
            phone TEXT,
            birth_date TEXT,
            age INTEGER,
            gender TEXT,
            occupation TEXT,
            address TEXT,
            systemic_conditions TEXT,
            notes TEXT,
            case_category TEXT,
            status TEXT DEFAULT 'جديد',
            case_notes TEXT,
            case_images TEXT,
            is_ongoing INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_DATE
        )
    """)
    
    # Migrations for clinic DBs
    clinic_columns = [
        ("status", "TEXT DEFAULT 'جديد'"),
        ("case_notes", "TEXT"),
        ("case_images", "TEXT")
    ]
    for col, ctype in clinic_columns:
        try: conn.execute(f"ALTER TABLE patients ADD COLUMN {col} {ctype}")
        except: pass
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER,
            agreed_price REAL DEFAULT 0,
            amount REAL DEFAULT 0,
            total_amount REAL DEFAULT 0,
            paid REAL DEFAULT 0,
            paid_amount REAL DEFAULT 0,
            payment_method TEXT DEFAULT 'Cash',
            date TEXT,
            status TEXT,
            notes TEXT
        )
    """)
    
    # Migrations for invoices
    inv_cols = [("amount", "REAL DEFAULT 0"), ("paid", "REAL DEFAULT 0")]
    for col, ctype in inv_cols:
        try: conn.execute(f"ALTER TABLE invoices ADD COLUMN {col} {ctype}")
        except: pass

    schema = [
        "CREATE TABLE IF NOT EXISTS appointments (id INTEGER PRIMARY KEY AUTOINCREMENT, patient_id INTEGER, date TEXT, time TEXT, type TEXT, duration_min INTEGER, status TEXT DEFAULT 'قادم', notes TEXT)",
        "CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT, role TEXT)",
        "CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)",
        "CREATE TABLE IF NOT EXISTS expenses (id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT, amount REAL, payment_method TEXT DEFAULT 'Cash', date TEXT, notes TEXT)",
        "CREATE TABLE IF NOT EXISTS teeth_map (patient_id INTEGER PRIMARY KEY, map_data TEXT)",
        "CREATE TABLE IF NOT EXISTS prescriptions (id INTEGER PRIMARY KEY AUTOINCREMENT, patient_id INTEGER, meds TEXT, notes TEXT, date TEXT, image_url TEXT)"
    ]
    for s in schema: conn.execute(s)
    
    # Indexes for performance
    conn.execute("CREATE INDEX IF NOT EXISTS idx_patients_name ON patients(first_name, last_name)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_patients_phone ON patients(phone)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_appointments_date ON appointments(date)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_invoices_patient ON invoices(patient_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(date)")

    # Migration for prescriptions
    try: conn.execute("ALTER TABLE prescriptions ADD COLUMN image_url TEXT")
    except: pass
    
    # Migrations for appointments
    apt_cols = [("duration_min", "INTEGER DEFAULT 30"), ("type", "TEXT"), ("notes", "TEXT"), ("status", "TEXT DEFAULT 'قادم'")]
    for col, ctype in apt_cols:
        try: conn.execute(f"ALTER TABLE appointments ADD COLUMN {col} {ctype}")
        except: pass
    
    # Smart Data Sync for Appointments (old columns to new)
    try:
        conn.execute("UPDATE appointments SET type = treatment WHERE type IS NULL AND treatment IS NOT NULL")
        conn.execute("UPDATE appointments SET duration_min = duration WHERE duration_min IS NULL AND duration IS NOT NULL")
    except: pass
    
    # Default Users
    conn.execute("INSERT OR IGNORE INTO users (username, password, role) VALUES ('admin', 'admin123', 'doctor')")
    conn.execute("INSERT OR IGNORE INTO users (username, password, role) VALUES ('staff', 'staff123', 'secretary')")
    conn.commit()

def db_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        g.db = get_db()
        
        # Security Check: Ensure the token was actually valid and parsed
        if getattr(g, 'user', None) is None:
            g.db.close()
            return jsonify({"error": "Unauthorized Access"}), 401
            
        try:
            return f(*args, **kwargs)
        finally:
            g.db.close()
    return decorated_function
