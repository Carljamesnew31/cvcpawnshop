"""One-time migration: local cvcpawnshop.db -> hosted PostgreSQL.

Usage (PowerShell):
    $env:DATABASE_URL = "postgresql://..."
    python migrate_to_postgres.py
"""
import os
import sqlite3
import base64
import mimetypes

DSN = os.environ.get('DATABASE_URL')
if not DSN:
    raise SystemExit('Set DATABASE_URL first.')

LOCAL_DB = os.environ.get('LOCAL_DB', 'cvcpawnshop.db')
UPLOAD_DIR = os.path.join('static', 'uploads')

# Importing app with DATABASE_URL set creates the tables in PostgreSQL.
os.environ.setdefault('DB_PATH', LOCAL_DB)
import app as m

src = sqlite3.connect(LOCAL_DB)
src.row_factory = sqlite3.Row


def columns(table):
    return [r[1] for r in src.execute(f'PRAGMA table_info({table})').fetchall()]


def to_data_uri(url):
    if not url or not str(url).startswith('/static/uploads/'):
        return url
    filename = os.path.basename(str(url))
    path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(path):
        return url
    mime = mimetypes.guess_type(path)[0] or 'image/jpeg'
    with open(path, 'rb') as f:
        data = base64.b64encode(f.read()).decode('ascii')
    return f'data:{mime};base64,{data}'


TABLES = {
    'inventory': ['id', 'code', 'name', 'category', 'description', 'condition',
                  'price', 'quantity', 'status', 'image_url', 'branch'],
    'sales': ['id', 'invoice_no', 'item_id', 'item_name', 'customer_name',
              'customer_contact', 'quantity', 'total_amount', 'payment_method',
              'sale_date', 'processed_by', 'branch'],
    'pawns': ['id', 'ticket_no', 'item_name', 'customer_name', 'customer_contact',
              'pawn_amount', 'pawn_date', 'due_date', 'status', 'total_paid',
              'branch', 'processed_by'],
    'pawn_payments': ['id', 'pawn_id', 'amount', 'payment_date', 'processed_by'],
    'audit_logs': ['id', 'username', 'action', 'details', 'timestamp'],
}

conn = m.get_db()
for table, cols in TABLES.items():
    available = columns(table)
    use_cols = [c for c in cols if c in available]
    placeholders = ','.join(['?'] * len(use_cols))
    sql = (f"INSERT INTO {table} ({','.join(use_cols)}) VALUES ({placeholders}) "
           f"ON CONFLICT (id) DO NOTHING")
    rows = src.execute(f"SELECT {','.join(use_cols)} FROM {table}").fetchall()
    for row in rows:
        values = [to_data_uri(row[c]) if c == 'image_url' else row[c] for c in use_cols]
        conn.execute(sql, tuple(values))
    conn.commit()
    print(f"{table}: {len(rows)} rows processed")

for table in TABLES:
    try:
        conn.execute(f"SELECT setval(pg_get_serial_sequence('{table}','id'), "
                     f"COALESCE((SELECT MAX(id) FROM {table}), 1))")
        conn.commit()
    except Exception as e:
        print(f"sequence reset skipped for {table}: {e}")

print("--- PostgreSQL row counts ---")
for table in TABLES:
    print(table, conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])

conn.close()
src.close()
