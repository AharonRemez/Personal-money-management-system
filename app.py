from flask import Flask, render_template, request, redirect
import sqlite3
import datetime
import os
import threading
import webview

app = Flask(__name__)

def init_db():
    if not os.path.exists('debts.db'):
        with sqlite3.connect('debts.db') as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE debts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    total_amount REAL NOT NULL,
                    remaining_amount REAL NOT NULL,
                    last_updated DATE NOT NULL
                )
            ''')
    else:
        # Check if the debts table needs to be altered to include new columns
        with sqlite3.connect('debts.db') as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(debts)")
            columns = [info[1] for info in cursor.fetchall()]
            if 'total_amount' not in columns or 'remaining_amount' not in columns:
                # Backup existing data
                cursor.execute("ALTER TABLE debts RENAME TO debts_backup")
                # Create new table with updated schema
                cursor.execute('''
                    CREATE TABLE debts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL UNIQUE,
                        total_amount REAL NOT NULL,
                        remaining_amount REAL NOT NULL,
                        last_updated DATE NOT NULL
                    )
                ''')
                # Migrate data from backup table
                cursor.execute("SELECT id, name, amount, last_updated FROM debts_backup")
                for row in cursor.fetchall():
                    debt_id, name, amount, last_updated = row
                    cursor.execute("INSERT INTO debts (id, name, total_amount, remaining_amount, last_updated) VALUES (?, ?, ?, ?, ?)",
                                   (debt_id, name, amount, amount, last_updated))
                # Drop backup table
                cursor.execute("DROP TABLE debts_backup")

@app.route('/', methods=['GET'])
def index():
    search_query = request.args.get('search', '').strip()
    with sqlite3.connect('debts.db') as conn:
        cursor = conn.cursor()
        if search_query:
            cursor.execute('''
                SELECT * FROM debts
                WHERE name LIKE ?
                ORDER BY
                    CASE WHEN remaining_amount > 0 THEN 0 ELSE 1 END,
                    id DESC
            ''', ('%' + search_query + '%',))
        else:
            cursor.execute('''
                SELECT * FROM debts
                ORDER BY
                    CASE WHEN remaining_amount > 0 THEN 0 ELSE 1 END,
                    id DESC
            ''')
        debts = cursor.fetchall()
    return render_template('index.html', debts=debts, search_query=search_query)

@app.route('/add', methods=['POST'])
def add_debt():
    name = request.form['name'].strip()
    amount = float(request.form['amount'])
    last_updated = datetime.date.today().isoformat()
    
    with sqlite3.connect('debts.db') as conn:
        cursor = conn.cursor()
        # Check if debt with this name already exists
        cursor.execute("SELECT * FROM debts WHERE name = ?", (name,))
        debt = cursor.fetchone()
        if debt:
            # Update existing debt
            new_total_amount = debt[2] + amount
            new_remaining_amount = debt[3] + amount
            cursor.execute("UPDATE debts SET total_amount = ?, remaining_amount = ?, last_updated = ? WHERE id = ?",
                           (new_total_amount, new_remaining_amount, last_updated, debt[0]))
        else:
            # Insert new debt
            cursor.execute("INSERT INTO debts (name, total_amount, remaining_amount, last_updated) VALUES (?, ?, ?, ?)",
                           (name, amount, amount, last_updated))
    return redirect('/')

@app.route('/update/<int:debt_id>', methods=['POST'])
def update_debt(debt_id):
    change_amount = float(request.form['amount'])
    action = request.form['action']
    last_updated = datetime.date.today().isoformat()
    
    with sqlite3.connect('debts.db') as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT total_amount, remaining_amount FROM debts WHERE id = ?", (debt_id,))
        debt = cursor.fetchone()
        if debt:
            total_amount = debt[0]
            remaining_amount = debt[1]
            
            if action == 'add':
                # Increase total_amount and remaining_amount
                total_amount += change_amount
                remaining_amount += change_amount
            elif action == 'subtract':
                # Decrease remaining_amount
                remaining_amount -= change_amount
            
            cursor.execute("UPDATE debts SET total_amount = ?, remaining_amount = ?, last_updated = ? WHERE id = ?",
                           (total_amount, remaining_amount, last_updated, debt_id))
    return redirect('/')

@app.route('/delete/<int:debt_id>', methods=['POST'])
def delete_debt(debt_id):
    with sqlite3.connect('debts.db') as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM debts WHERE id = ?", (debt_id,))
    return redirect('/')

@app.route('/stats')
def stats():
    with sqlite3.connect('debts.db') as conn:
        cursor = conn.cursor()
        # Total number of debts
        cursor.execute("SELECT COUNT(*) FROM debts")
        total_debts = cursor.fetchone()[0] or 0
        # Total amount owed (sum of total_amount)
        cursor.execute("SELECT SUM(total_amount) FROM debts")
        total_amount_owed = cursor.fetchone()[0] or 0
        # Total remaining amount to be repaid
        cursor.execute("SELECT SUM(remaining_amount) FROM debts")
        total_remaining_amount = cursor.fetchone()[0] or 0
        # Total amount repaid
        total_amount_repaid = total_amount_owed - total_remaining_amount
    return render_template('stats.html', total_debts=total_debts, total_amount_owed=total_amount_owed,
                           total_remaining_amount=total_remaining_amount, total_amount_repaid=total_amount_repaid)

def run_flask():
    app.run()

def on_closed():
    os._exit(0)

if __name__ == '__main__':
    init_db()
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # Create window with PyWebView
    window = webview.create_window('ניהול כסף', 'http://127.0.0.1:5000')

    # Add event listener for window closed
    window.events.closed += on_closed

    # Start PyWebView
    webview.start(debug=False, http_server=True)
