import sqlite3
import os

DB_PATH = r"c:\Users\Dell\Desktop\claude 1 - Copy - Copy\dental-clinic\databases\clinic_doctor.db"

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("--- Tables ---")
tables = cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
for t in tables:
    print(t['name'])
    count = cur.execute(f"SELECT COUNT(*) as c FROM {t['name']}").fetchone()
    print(f"  Count: {count['c']}")

print("\n--- Patients Sample ---")
patients = cur.execute("SELECT * FROM patients LIMIT 5").fetchall()
for p in patients:
    print(dict(p))

conn.close()
