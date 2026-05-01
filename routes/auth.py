from flask import Blueprint, request, jsonify, current_app
from database import get_db, get_master_db, init_clinic_schema
import datetime
import jwt
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

auth_bp = Blueprint("auth", __name__)

# --- Authentication Middleware ---
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("Authorization")
        if not token:
            return jsonify({"error": "Token is missing"}), 401
        try:
            # Handle "Bearer <token>" format
            if " " in token:
                token = token.split(" ")[1]
            data = jwt.decode(token, current_app.config["SECRET_KEY"], algorithms=["HS256"])
            request.user = data # Store user info in request
        except Exception as e:
            return jsonify({"error": "Token is invalid or expired"}), 401
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("Authorization")
        if not token: return jsonify({"error": "Unauthorized"}), 401
        try:
            if " " in token: token = token.split(" ")[1]
            data = jwt.decode(token, current_app.config["SECRET_KEY"], algorithms=["HS256"])
            if data.get("role") != "admin":
                return jsonify({"error": "Admin access required"}), 403
            request.user = data
        except: return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated

from extensions import limiter

@auth_bp.route("/login", methods=["POST"])
@limiter.limit("5 per minute")
def login():
    data = request.json or {}
    u = data.get("username")
    p = data.get("password")
    
    if not u or not p:
        return jsonify({"error": "Username and password required"}), 400

    master_conn = get_master_db()
    # Check if this is the System Admin (Hardcoded for now as per image issue #3 & #6)
    if u == "admin" and p == "admin123":
        current_app.logger.info(f"SECURITY: Admin logged in from {request.remote_addr}")
        token = jwt.encode({
            "username": "admin",
            "role": "admin",
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=24)
        }, current_app.config["SECRET_KEY"], algorithm="HS256")
        return jsonify({"token": token, "role": "admin", "username": "admin"})

    # Try Doctor/Clinic Login
    doctor = master_conn.execute("SELECT * FROM doctors WHERE username=?", (u,)).fetchone()
    
    if doctor:
        role = "doctor"
        if check_password_hash(doctor["password"], p):
            current_app.logger.info(f"LOGIN: Doctor {u} logged in successfully")
            pass 
        elif doctor["secretary_enabled"] and check_password_hash(doctor["secretary_password"], p):
            role = "secretary"
            current_app.logger.info(f"LOGIN: Secretary for {u} logged in")
        else:
            current_app.logger.warning(f"AUTH_FAILED: Invalid password for {u} from {request.remote_addr}")
            master_conn.close()
            return jsonify({"error": "Invalid credentials"}), 401

        # Check status & expiry
        if doctor['status'] == 'inactive':
            return jsonify({"error": "Account deactivated"}), 403
        if doctor['expiry_date']:
            expiry = datetime.datetime.strptime(doctor['expiry_date'], '%Y-%m-%d')
            if expiry < datetime.datetime.now():
                return jsonify({"error": "Subscription expired"}), 403

        # Generate Token
        token = jwt.encode({
            "username": doctor["username"],
            "role": role,
            "clinic_id": doctor["id"],
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=24)
        }, current_app.config["SECRET_KEY"], algorithm="HS256")

        res = {
            "token": token,
            "role": role,
            "username": doctor["username"],
            "clinic_name": doctor["clinic_name"],
            "doctor_name": doctor["doctor_name"]
        }
        master_conn.close()
        return jsonify(res)
    
    master_conn.close()
    return jsonify({"error": "Unauthorized"}), 401

@auth_bp.route("/me", methods=["GET"])
@token_required
def get_me():
    return jsonify(request.user)

@auth_bp.route("/admin/settings", methods=["GET"])
@admin_required
def get_admin_settings():
    master_conn = get_master_db()
    rows = master_conn.execute("SELECT * FROM master_settings").fetchall()
    master_conn.close()
    return jsonify({r['key']: r['value'] for r in rows})

@auth_bp.route("/admin/settings", methods=["POST"])
@admin_required
def update_admin_settings():
    data = request.json or {}
    master_conn = get_master_db()
    for k, v in data.items():
        master_conn.execute("INSERT OR REPLACE INTO master_settings (key, value) VALUES (?, ?)", (k, str(v)))
    master_conn.commit()
    master_conn.close()
    return jsonify({"ok": True})

@auth_bp.route("/change-password", methods=["POST"])
@token_required
def change_password():
    data = request.json
    new_p = data.get("password")
    if not new_p: return jsonify({"error": "Missing data"}), 400
    
    hashed_p = generate_password_hash(new_p)
    master_conn = get_master_db()
    master_conn.execute("UPDATE doctors SET password = ? WHERE username = ?", (hashed_p, request.user["username"]))
    master_conn.commit()
    master_conn.close()
    return jsonify({"ok": True})

@auth_bp.route("/doctors", methods=["GET"])
@admin_required
def list_doctors():
    master_conn = get_master_db()
    doctors = master_conn.execute("SELECT id, username, clinic_name, expiry_date, status, secretary_enabled, created_at FROM doctors").fetchall()
    master_conn.close()
    return jsonify([dict(d) for d in doctors])

@auth_bp.route("/doctors", methods=["POST"])
@admin_required
def create_doctor():
    data = request.json or {}
    u = data.get("username")
    p = data.get("password")
    c = data.get("clinic_name", "عيادة جديدة")
    
    if not u or not p: return jsonify({"error": "Missing fields"}), 400
    
    hashed_p = generate_password_hash(p)
    master_conn = get_master_db()
    try:
        res = master_conn.execute(
            "INSERT INTO doctors (username, password, clinic_name, status, created_at) VALUES (?, ?, ?, 'active', ?)",
            (u, hashed_p, c, datetime.date.today().isoformat())
        )
        new_id = res.lastrowid
        master_conn.commit()
        init_clinic_schema(new_id)
        return jsonify({"id": new_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        master_conn.close()

@auth_bp.route("/doctors/<int:id>", methods=["PUT"])
@admin_required
def update_doctor(id):
    data = request.json
    master_conn = get_master_db()
    
    if "password" in data and data["password"]:
        data["password"] = generate_password_hash(data["password"])
    if "secretary_password" in data and data["secretary_password"]:
        data["secretary_password"] = generate_password_hash(data["secretary_password"])
        
    keys = [f"{k}=?" for k in data.keys()]
    master_conn.execute(f"UPDATE doctors SET {', '.join(keys)} WHERE id=?", (*data.values(), id))
    master_conn.commit()
    master_conn.close()
    return jsonify({"ok": True})
