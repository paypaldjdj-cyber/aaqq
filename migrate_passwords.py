import sqlite3
import os
from werkzeug.security import generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "..", "databases", "master.db")

def migrate_passwords():
    if not os.path.exists(DB_PATH):
        print("Database not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    doctors = cursor.execute("SELECT id, password, secretary_password FROM doctors").fetchall()

    for doctor in doctors:
        updates = []
        params = []

        # Hash main password if not already hashed (hashes start with pbkdf2:sha256: or scrypt: or argon2:)
        if doctor["password"] and not doctor["password"].startswith(("pbkdf2:", "scrypt:", "argon2:")):
            hashed = generate_password_hash(doctor["password"])
            updates.append("password = ?")
            params.append(hashed)
            print(f"Hashed main password for ID {doctor['id']}")

        # Hash secretary password
        if doctor["secretary_password"] and not doctor["secretary_password"].startswith(("pbkdf2:", "scrypt:", "argon2:")):
            hashed_sec = generate_password_hash(doctor["secretary_password"])
            updates.append("secretary_password = ?")
            params.append(hashed_sec)
            print(f"Hashed secretary password for ID {doctor['id']}")

        if updates:
            params.append(doctor["id"])
            cursor.execute(f"UPDATE doctors SET {', '.join(updates)} WHERE id = ?", params)

    conn.commit()
    conn.close()
    print("Migration completed.")

if __name__ == "__main__":
    migrate_passwords()
