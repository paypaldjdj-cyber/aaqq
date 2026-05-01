import sqlite3
c = sqlite3.connect('clinic.db')
rows = c.execute("SELECT id, first_name, last_name, phone FROM patients WHERE (first_name LIKE '%%' OR last_name LIKE '%%' OR phone LIKE '%%')").fetchall()
print("Query Result:", rows)
