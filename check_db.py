import sqlite3

# Подключаемся к базе бота
conn = sqlite3.connect('appointments.db')
cursor = conn.cursor()

print("--- СПИСОК ПАЦИЕНТОВ В БАЗЕ БОТА ---")
cursor.execute("SELECT first_name, date, time, appointment_id FROM appointments")
for row in cursor.fetchall():
    print(f"Имя: {row[0]} | Дата: {row[1]} {row[2]} | ID в базе: {row[3]}")

conn.close()