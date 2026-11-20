from flask import Flask, render_template, request, redirect, url_for, session, send_file, Response
import sqlite3
from datetime import datetime, timedelta
import uuid
import os
import base64
import json
from io import BytesIO
from PIL import Image

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'cvcpawnshop_secret_key')
DB_PATH = os.environ.get('DB_PATH', 'cvcpawnshop.db')
DATABASE_URL = os.environ.get('DATABASE_URL')
USE_POSTGRES = bool(DATABASE_URL)

if USE_POSTGRES:
    import psycopg2
    import psycopg2.extras

# Set these as environment variables on the host so the public repo never
# contains the live credentials. Locally the defaults keep development easy.
USERS = {
    os.environ.get('OWNER_USER', 'Chezl'): (os.environ.get('OWNER_PASS', 'chezl123'), 'owner'),
    os.environ.get('STAFF1_USER', 'Chanda'): (os.environ.get('STAFF1_PASS', 'chanda123'), 'staff'),
    os.environ.get('STAFF2_USER', 'Kenrose'): (os.environ.get('STAFF2_PASS', 'kenrose123'), 'staff'),
}


def _pg_sql(sql):
    """Translate the app's SQLite-flavoured SQL into PostgreSQL."""
    sql = sql.replace('?', '%s')
    sql = sql.replace('id INTEGER PRIMARY KEY AUTOINCREMENT', 'id SERIAL PRIMARY KEY')
    sql = sql.replace("date(sale_date) = date('now')", "date(sale_date) = CURRENT_DATE")
    sql = sql.replace("strftime('%Y-%m', sale_date) = strftime('%Y-%m','now')",
                      "to_char(sale_date::date, 'YYYY-MM') = to_char(CURRENT_DATE, 'YYYY-MM')")
    sql = sql.replace("strftime('%Y', sale_date) = strftime('%Y','now')",
                      "EXTRACT(YEAR FROM sale_date::date) = EXTRACT(YEAR FROM CURRENT_DATE)")
    return sql


class PGConnection:
    """Small wrapper so psycopg2 behaves like the sqlite3 connection used below."""

    def __init__(self, dsn):
        self._conn = psycopg2.connect(dsn, cursor_factory=psycopg2.extras.DictCursor)

    def execute(self, sql, params=()):
        cur = self._conn.cursor()
        cur.execute(_pg_sql(sql), params)
        return cur

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def __del__(self):
        # Release the connection even if a route raises before calling close().
        try:
            self._conn.close()
        except Exception:
            pass


def get_db():
    if USE_POSTGRES:
        return PGConnection(DATABASE_URL)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute('''CREATE TABLE IF NOT EXISTS inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE,
        name TEXT,
        category TEXT,
        description TEXT,
        condition TEXT,
        price REAL,
        quantity INTEGER,
        status TEXT,
        image_url TEXT,
        branch TEXT
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_no TEXT UNIQUE,
        item_id INTEGER,
        item_name TEXT,
        customer_name TEXT,
        customer_contact TEXT,
        quantity INTEGER,
        total_amount REAL,
        payment_method TEXT,
        sale_date TEXT,
        processed_by TEXT,
        branch TEXT
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        action TEXT,
        details TEXT,
        timestamp TEXT
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS pawns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_no TEXT UNIQUE,
        item_name TEXT,
        customer_name TEXT,
        customer_contact TEXT,
        pawn_amount REAL,
        pawn_date TEXT,
        due_date TEXT,
        status TEXT,
        total_paid REAL,
        branch TEXT,
        processed_by TEXT
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS pawn_payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pawn_id INTEGER,
        amount REAL,
        payment_date TEXT,
        processed_by TEXT
    )''')
    conn.commit()
    conn.close()


def audit(username, action, details):
    conn = get_db()
    conn.execute("INSERT INTO audit_logs (username, action, details, timestamp) VALUES (?,?,?,?)",
                 (username, action, details, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()


init_db()


@app.route('/')
def home():
    conn = get_db()
    items = conn.execute("SELECT * FROM inventory WHERE status='Available' AND quantity > 0").fetchall()
    conn.close()
    return render_template('home.html', items=items)


@app.route('/remate')
def remate():
    conn = get_db()
    items = conn.execute("SELECT * FROM inventory WHERE status='Available' AND quantity > 0").fetchall()
    conn.close()
    return render_template('remate.html', items=items)


@app.route('/contact')
def contact():
    return render_template('contact.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u = request.form['username']; p = request.form['password']
        if u in USERS and USERS[u][0] == p:
            session['user'] = u; session['role'] = USERS[u][1]
            return redirect(url_for('admin'))
    return '''
    <form method="post" style="max-width:300px;margin:100px auto;font-family:sans-serif;">
      <h2>CVCPawnshop Login</h2>
      <input type="text" name="username" placeholder="Username (owner/staff)" required style="width:100%;padding:8px;margin:5px 0;"><br>
      <input type="password" name="password" placeholder="Password" required style="width:100%;padding:8px;margin:5px 0;"><br>
      <button type="submit" style="width:100%;padding:10px;background:#1e3a8a;color:white;border:none;">Login</button>
    </form>
    '''


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))


@app.route('/admin')
def admin():
    if not session.get('user'):
        return redirect(url_for('login'))
    role = session.get('role')
    search = request.args.get('search', '')
    conn = get_db()
    if search:
        items = conn.execute("SELECT * FROM inventory WHERE name LIKE ? OR code LIKE ?", (f'%{search}%', f'%{search}%')).fetchall()
    else:
        items = conn.execute("SELECT * FROM inventory").fetchall()
    sales = conn.execute("SELECT * FROM sales ORDER BY id DESC").fetchall()
    row = conn.execute("SELECT SUM(total_amount) FROM sales WHERE date(sale_date) = date('now')").fetchone()
    daily_sales = row[0] if row and row[0] else 0
    total_sales = conn.execute("SELECT SUM(total_amount) FROM sales").fetchone()[0] or 0
    monthly_sales = conn.execute("SELECT SUM(total_amount) FROM sales WHERE strftime('%Y-%m', sale_date) = strftime('%Y-%m','now')").fetchone()[0] or 0
    yearly_sales = conn.execute("SELECT SUM(total_amount) FROM sales WHERE strftime('%Y', sale_date) = strftime('%Y','now')").fetchone()[0] or 0
    pawns = conn.execute("SELECT * FROM pawns ORDER BY id DESC").fetchall()
    audit_logs = conn.execute("SELECT * FROM audit_logs ORDER BY id DESC").fetchall() if role == 'owner' else []
    conn.close()
    return render_template('admin.html', items=items, sales=sales, daily_sales=daily_sales,
                           total_sales=total_sales, monthly_sales=monthly_sales, yearly_sales=yearly_sales,
                           pawns=pawns, audit_logs=audit_logs, role=role, user=session.get('user'))


@app.route('/add_item', methods=['POST'])
def add_item():
    if not session.get('user'):
        return redirect(url_for('login'))
    code = request.form.get('code', '').strip()
    if not code:
        cat = request.form.get('category', 'ITEM').strip().upper()[:4] or 'ITEM'
        conn_tmp = get_db()
        i = 1
        while True:
            cand = f"{cat}-{str(i).zfill(3)}"
            exists = conn_tmp.execute("SELECT 1 FROM inventory WHERE code=?", (cand,)).fetchone()
            if not exists:
                code = cand
                break
            i += 1
        conn_tmp.close()
    image_url = request.form.get('image_url', '').strip()
    file = request.files.get('image_file')
    if file and file.filename:
        # Store the resized image inside the database as a data URI so it survives
        # restarts on hosts with an ephemeral filesystem.
        img = Image.open(file)
        img = img.convert('RGB')
        img = img.resize((400, 240))
        buf = BytesIO()
        img.save(buf, format='JPEG', quality=85)
        image_url = 'data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')
    if not image_url:
        image_url = 'https://via.placeholder.com/400x240?text=No+Image'
    conn = get_db()
    branch = request.form.get('branch', 'CVC Opon')
    conn.execute('''INSERT INTO inventory (code, name, category, description, condition, price, quantity, status, image_url, branch)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'Available', ?, ?)''',
                 (code, request.form['name'], request.form['category'],
                  request.form['description'], request.form['condition'], float(request.form['price']),
                  int(request.form['quantity']), image_url, branch))
    conn.commit()
    conn.close()
    audit(session.get('user'), 'ADD_ITEM', f"Added item {code} - {request.form['name']} at {branch}")
    return redirect(url_for('admin'))


@app.route('/delete_item/<int:id>')
def delete_item(id):
    if session.get('role') != 'owner':
        return redirect(url_for('login'))
    conn = get_db()
    item = conn.execute("SELECT * FROM inventory WHERE id=?", (id,)).fetchone()
    conn.execute("DELETE FROM inventory WHERE id=?", (id,))
    conn.commit()
    conn.close()
    audit(session.get('user'), 'DELETE_ITEM', f"Deleted item {item['code'] if item else id} - {item['name'] if item else ''}")
    return redirect(url_for('admin'))


@app.route('/delete_sale/<int:id>')
def delete_sale(id):
    if session.get('role') != 'owner':
        return redirect(url_for('login'))
    conn = get_db()
    sale = conn.execute("SELECT * FROM sales WHERE id=?", (id,)).fetchone()
    conn.execute("DELETE FROM sales WHERE id=?", (id,))
    conn.commit()
    conn.close()
    audit(session.get('user'), 'DELETE_SALE', f"Deleted sale {sale['invoice_no'] if sale else id}")
    return redirect(url_for('admin'))


@app.route('/delete_pawn/<int:id>')
def delete_pawn(id):
    if session.get('role') != 'owner':
        return redirect(url_for('login'))
    conn = get_db()
    pawn = conn.execute("SELECT * FROM pawns WHERE id=?", (id,)).fetchone()
    conn.execute("DELETE FROM pawn_payments WHERE pawn_id=?", (id,))
    conn.execute("DELETE FROM pawns WHERE id=?", (id,))
    conn.commit()
    conn.close()
    audit(session.get('user'), 'DELETE_PAWN', f"Deleted pawn {pawn['ticket_no'] if pawn else id}")
    return redirect(url_for('admin'))


@app.route('/new_sale', methods=['POST'])
def new_sale():
    if not session.get('user'):
        return redirect(url_for('login'))
    item_id = int(request.form['item_id'])
    qty = int(request.form['quantity'])
    user = session.get('user')
    conn = get_db()
    item = conn.execute("SELECT * FROM inventory WHERE id=?", (item_id,)).fetchone()
    if item and item['quantity'] >= qty:
        total = item['price'] * qty
        invoice_no = "INV-" + uuid.uuid4().hex[:6].upper()
        sale_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        branch = request.form.get('branch', 'CVC Opon')
        conn.execute('''INSERT INTO sales (invoice_no, item_id, item_name, customer_name, customer_contact, quantity, total_amount, payment_method, sale_date, processed_by, branch)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                     (invoice_no, item_id, item['name'], request.form['customer_name'],
                      request.form['customer_contact'], qty, total, request.form['payment_method'], sale_date, user, branch))
        new_qty = item['quantity'] - qty
        new_status = 'Sold' if new_qty == 0 else 'Available'
        conn.execute("UPDATE inventory SET quantity=?, status=? WHERE id=?", (new_qty, new_status, item_id))
        conn.commit()
        conn.close()
        audit(user, 'SALE', f"Sold {qty} x {item['name']} (Invoice {invoice_no}) at {branch}")
        return redirect(url_for('invoice', invoice_no=invoice_no))
    conn.close()
    return redirect(url_for('admin'))


@app.route('/new_pawn', methods=['POST'])
def new_pawn():
    if not session.get('user'):
        return redirect(url_for('login'))
    user = session.get('user')
    branch = request.form.get('branch', 'CVC Opon')
    pawn_date = datetime.now()
    due_date = pawn_date + timedelta(days=30)
    ticket = "PAWN-" + uuid.uuid4().hex[:6].upper()
    conn = get_db()
    conn.execute('''INSERT INTO pawns (ticket_no, item_name, customer_name, customer_contact, pawn_amount, pawn_date, due_date, status, total_paid, branch, processed_by)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
                 (ticket, request.form['item_name'], request.form['customer_name'], request.form['customer_contact'],
                  float(request.form['pawn_amount']), pawn_date.strftime("%Y-%m-%d"), due_date.strftime("%Y-%m-%d"),
                  'Active', 0, branch, user))
    conn.commit()
    conn.close()
    audit(user, 'PAWN', f"New pawn {ticket} for {request.form['item_name']} due {due_date.strftime('%Y-%m-%d')} at {branch}")
    print(f"[SMS] To owner: New pawn {ticket} - {request.form['item_name']} due {due_date.strftime('%Y-%m-%d')} at {branch}, customer {request.form['customer_name']} ({request.form['customer_contact']})")
    return redirect(url_for('admin'))


@app.route('/renew_pawn/<int:id>', methods=['POST'])
def renew_pawn(id):
    if not session.get('user'):
        return redirect(url_for('login'))
    user = session.get('user')
    amt = float(request.form['amount'])
    conn = get_db()
    pawn = conn.execute("SELECT * FROM pawns WHERE id=?", (id,)).fetchone()
    if pawn:
        new_due = datetime.strptime(pawn['due_date'], "%Y-%m-%d") + timedelta(days=7)
        conn.execute("UPDATE pawns SET due_date=?, total_paid=total_paid+?, status='Active' WHERE id=?",
                     (new_due.strftime("%Y-%m-%d"), amt, id))
        conn.execute("INSERT INTO pawn_payments (pawn_id, amount, payment_date, processed_by) VALUES (?,?,?,?)",
                     (id, amt, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user))
        conn.commit()
        audit(user, 'RENEW', f"Renewed pawn {pawn['ticket_no']} +₱{amt:.2f}, new due {new_due.strftime('%Y-%m-%d')}")
    conn.close()
    return redirect(url_for('admin'))


@app.route('/invoice/<invoice_no>')
def invoice(invoice_no):
    if not session.get('user'):
        return redirect(url_for('login'))
    conn = get_db()
    sale = conn.execute("SELECT * FROM sales WHERE invoice_no=?", (invoice_no,)).fetchone()
    conn.close()
    return render_template('invoice.html', sale=sale)


@app.route('/backup')
def backup():
    if session.get('role') != 'owner':
        return redirect(url_for('login'))
    audit(session.get('user'), 'BACKUP', 'Downloaded database backup')
    if USE_POSTGRES:
        conn = get_db()
        data = {}
        for table in ('inventory', 'sales', 'pawns', 'pawn_payments', 'audit_logs'):
            data[table] = [dict(row) for row in conn.execute(f"SELECT * FROM {table}").fetchall()]
        conn.close()
        return Response(json.dumps(data, default=str, indent=2), mimetype='application/json',
                        headers={'Content-Disposition': 'attachment; filename=cvcpawnshop_backup.json'})
    return send_file(DB_PATH, as_attachment=True, download_name='cvcpawnshop_backup.db')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)),
            debug=os.environ.get('FLASK_DEBUG') == '1')
