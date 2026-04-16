import os, json, hashlib, math
from datetime import datetime

DATABASE_URL = ""
try:
    import streamlit as st
    DATABASE_URL = st.secrets.get("DATABASE_URL", os.environ.get("DATABASE_URL", ""))
except Exception:
    DATABASE_URL = os.environ.get("DATABASE_URL", "")

USE_PG = bool(DATABASE_URL)
DB_PATH = "financas.db"
PH = "%s" if USE_PG else "?"

def _conn():
    if USE_PG:
        import psycopg2, psycopg2.extras
        return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    import sqlite3
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row; return c

def _exec(sql, params=()):
    with _conn() as c:
        cur = c.cursor(); cur.execute(sql, params); c.commit()
        if USE_PG:
            try: return cur.fetchone()["id"]
            except: return None
        return cur.lastrowid

def _fetch(sql, params=()):
    with _conn() as c:
        cur = c.cursor(); cur.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]

def _one(sql, params=()):
    with _conn() as c:
        cur = c.cursor(); cur.execute(sql, params)
        r = cur.fetchone(); return dict(r) if r else None

def hp(pwd): return hashlib.sha256(pwd.encode()).hexdigest()

def init_db():
    if USE_PG: _init_pg()
    else: _init_sq()

# ── Supabase SQL (copie e cole no SQL Editor do Supabase) ────────────────────
SUPABASE_SQL = """
-- Cole este SQL no Supabase > SQL Editor > New query > Run

CREATE TABLE IF NOT EXISTS config(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS income(id SERIAL PRIMARY KEY, month TEXT, label TEXT, amount FLOAT DEFAULT 0, due_day INT DEFAULT 30);
CREATE TABLE IF NOT EXISTS fixed_expenses(id SERIAL PRIMARY KEY, month TEXT, label TEXT, amount FLOAT DEFAULT 0, due_day INT DEFAULT 30, category TEXT DEFAULT 'Outros');
CREATE TABLE IF NOT EXISTS credit_card_items(id SERIAL PRIMARY KEY, label TEXT, total_amount FLOAT, installments INT DEFAULT 1, start_month TEXT, card_name TEXT DEFAULT 'Cartão Principal', created_at TIMESTAMPTZ DEFAULT NOW());
CREATE TABLE IF NOT EXISTS extra_expenses(id SERIAL PRIMARY KEY, month TEXT, label TEXT, amount FLOAT DEFAULT 0, category TEXT DEFAULT 'Outros', payment_method TEXT DEFAULT 'PIX', expense_type TEXT DEFAULT 'extra');
CREATE TABLE IF NOT EXISTS subscriptions(id SERIAL PRIMARY KEY, label TEXT, amount FLOAT DEFAULT 0, category TEXT DEFAULT 'Entretenimento', billing_day INT DEFAULT 1, active INT DEFAULT 1, notes TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS debts(id SERIAL PRIMARY KEY, label TEXT, total_amount FLOAT, remaining_amount FLOAT, monthly_payment FLOAT DEFAULT 0, interest_rate FLOAT DEFAULT 0, due_day INT DEFAULT 30, notes TEXT DEFAULT '', created_at TIMESTAMPTZ DEFAULT NOW());
CREATE TABLE IF NOT EXISTS investments(id SERIAL PRIMARY KEY, month TEXT UNIQUE, amount_added FLOAT DEFAULT 0, total_accumulated FLOAT DEFAULT 0, investment_type TEXT DEFAULT 'Renda Fixa', investment_source TEXT DEFAULT 'Renda do mês', due_day INT DEFAULT 30, notes TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS insurance(id SERIAL PRIMARY KEY, label TEXT, provider TEXT DEFAULT '', monthly_cost FLOAT DEFAULT 0, coverage TEXT DEFAULT '', due_day INT DEFAULT 30, notes TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS goals(id SERIAL PRIMARY KEY, label TEXT, target_amount FLOAT, current_amount FLOAT DEFAULT 0, deadline TEXT DEFAULT '', notes TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS emergency_fund(id SERIAL PRIMARY KEY, month TEXT UNIQUE, balance FLOAT DEFAULT 0);
CREATE TABLE IF NOT EXISTS bill_templates(id SERIAL PRIMARY KEY, label TEXT, estimated_amount FLOAT DEFAULT 0, category TEXT DEFAULT 'Utilidades', due_day INT DEFAULT 10, active INT DEFAULT 1);
CREATE TABLE IF NOT EXISTS bills(id SERIAL PRIMARY KEY, month TEXT, label TEXT, amount FLOAT DEFAULT 0, category TEXT DEFAULT 'Utilidades', due_day INT DEFAULT 10);
CREATE TABLE IF NOT EXISTS payments(id SERIAL PRIMARY KEY, month TEXT, item_type TEXT, item_id INT, item_label TEXT, amount FLOAT DEFAULT 0, paid INT DEFAULT 0, paid_at TEXT, UNIQUE(month, item_type, item_id));
CREATE TABLE IF NOT EXISTS edit_history(id SERIAL PRIMARY KEY, operation TEXT, table_name TEXT, record_id INT, data_before TEXT, created_at TIMESTAMPTZ DEFAULT NOW());

-- Senha padrão 1234 (SHA-256)
INSERT INTO config VALUES('password','03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4') ON CONFLICT(key) DO NOTHING;
"""

def _init_pg():
    import psycopg2
    c = psycopg2.connect(DATABASE_URL); cur = c.cursor()
    # Create tables (idempotent)
    stmts = [s.strip() for s in SUPABASE_SQL.split(";") if s.strip() and not s.strip().startswith("--")]
    for s in stmts:
        try: cur.execute(s); c.commit()
        except: c.rollback()
    c.close()

def _init_sq():
    import sqlite3
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.executescript("""
    CREATE TABLE IF NOT EXISTS config(key TEXT PRIMARY KEY, value TEXT);
    CREATE TABLE IF NOT EXISTS income(id INTEGER PRIMARY KEY AUTOINCREMENT, month TEXT, label TEXT, amount REAL DEFAULT 0, due_day INTEGER DEFAULT 30);
    CREATE TABLE IF NOT EXISTS fixed_expenses(id INTEGER PRIMARY KEY AUTOINCREMENT, month TEXT, label TEXT, amount REAL DEFAULT 0, due_day INTEGER DEFAULT 30, category TEXT DEFAULT 'Outros');
    CREATE TABLE IF NOT EXISTS credit_card_items(id INTEGER PRIMARY KEY AUTOINCREMENT, label TEXT, total_amount REAL, installments INTEGER DEFAULT 1, start_month TEXT, card_name TEXT DEFAULT 'Cartão Principal', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS extra_expenses(id INTEGER PRIMARY KEY AUTOINCREMENT, month TEXT, label TEXT, amount REAL DEFAULT 0, category TEXT DEFAULT 'Outros', payment_method TEXT DEFAULT 'PIX', expense_type TEXT DEFAULT 'extra');
    CREATE TABLE IF NOT EXISTS subscriptions(id INTEGER PRIMARY KEY AUTOINCREMENT, label TEXT, amount REAL DEFAULT 0, category TEXT DEFAULT 'Entretenimento', billing_day INTEGER DEFAULT 1, active INTEGER DEFAULT 1, notes TEXT DEFAULT '');
    CREATE TABLE IF NOT EXISTS debts(id INTEGER PRIMARY KEY AUTOINCREMENT, label TEXT, total_amount REAL, remaining_amount REAL, monthly_payment REAL DEFAULT 0, interest_rate REAL DEFAULT 0, due_day INTEGER DEFAULT 30, notes TEXT DEFAULT '', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS investments(id INTEGER PRIMARY KEY AUTOINCREMENT, month TEXT UNIQUE, amount_added REAL DEFAULT 0, total_accumulated REAL DEFAULT 0, investment_type TEXT DEFAULT 'Renda Fixa', investment_source TEXT DEFAULT 'Renda do mês', due_day INTEGER DEFAULT 30, notes TEXT DEFAULT '');
    CREATE TABLE IF NOT EXISTS insurance(id INTEGER PRIMARY KEY AUTOINCREMENT, label TEXT, provider TEXT DEFAULT '', monthly_cost REAL DEFAULT 0, coverage TEXT DEFAULT '', due_day INTEGER DEFAULT 30, notes TEXT DEFAULT '');
    CREATE TABLE IF NOT EXISTS goals(id INTEGER PRIMARY KEY AUTOINCREMENT, label TEXT, target_amount REAL, current_amount REAL DEFAULT 0, deadline TEXT DEFAULT '', notes TEXT DEFAULT '');
    CREATE TABLE IF NOT EXISTS emergency_fund(id INTEGER PRIMARY KEY AUTOINCREMENT, month TEXT UNIQUE, balance REAL DEFAULT 0);
    CREATE TABLE IF NOT EXISTS bill_templates(id INTEGER PRIMARY KEY AUTOINCREMENT, label TEXT, estimated_amount REAL DEFAULT 0, category TEXT DEFAULT 'Utilidades', due_day INTEGER DEFAULT 10, active INTEGER DEFAULT 1);
    CREATE TABLE IF NOT EXISTS bills(id INTEGER PRIMARY KEY AUTOINCREMENT, month TEXT, label TEXT, amount REAL DEFAULT 0, category TEXT DEFAULT 'Utilidades', due_day INTEGER DEFAULT 10);
    CREATE TABLE IF NOT EXISTS payments(id INTEGER PRIMARY KEY AUTOINCREMENT, month TEXT, item_type TEXT, item_id INTEGER, item_label TEXT, amount REAL DEFAULT 0, paid INTEGER DEFAULT 0, paid_at TEXT, UNIQUE(month, item_type, item_id));
    CREATE TABLE IF NOT EXISTS edit_history(id INTEGER PRIMARY KEY AUTOINCREMENT, operation TEXT, table_name TEXT, record_id INTEGER, data_before TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    """)
    # Migrations for existing DBs
    for col, tbl, defval in [
        ("expense_type TEXT DEFAULT 'extra'", "extra_expenses", None),
        ("investment_source TEXT DEFAULT 'Renda do mês'", "investments", None),
        ("due_day INTEGER DEFAULT 30", "investments", None),
        ("due_day INTEGER DEFAULT 30", "insurance", None),
        ("due_day INTEGER DEFAULT 30", "debts", None),
    ]:
        col_name = col.split()[0]
        try: c.execute(f"ALTER TABLE {tbl} ADD COLUMN {col}")
        except: pass
    c.commit()
    if not c.execute("SELECT 1 FROM config WHERE key='password'").fetchone():
        c.execute("INSERT INTO config VALUES('password',?)", (hp("1234"),))
    c.commit(); c.close()

# ── Auth ─────────────────────────────────────────────────────────────────────
def check_pwd(pwd):
    r = _one(f"SELECT value FROM config WHERE key={PH}", ("password",))
    return bool(r) and r["value"] == hp(pwd)

def change_pwd(new):
    if USE_PG: _exec(f"INSERT INTO config(key,value) VALUES({PH},{PH}) ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value", ("password", hp(new)))
    else: _exec(f"INSERT OR REPLACE INTO config VALUES({PH},{PH})", ("password", hp(new)))

def get_api_key():
    r = _one(f"SELECT value FROM config WHERE key={PH}", ("api_key",)); return r["value"] if r else ""

def set_api_key(k):
    if USE_PG: _exec(f"INSERT INTO config(key,value) VALUES({PH},{PH}) ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value", ("api_key", k))
    else: _exec(f"INSERT OR REPLACE INTO config VALUES({PH},{PH})", ("api_key", k))

def get_config(key, default=""):
    r = _one(f"SELECT value FROM config WHERE key={PH}", (key,)); return r["value"] if r else default

def set_config(key, value):
    if USE_PG: _exec(f"INSERT INTO config(key,value) VALUES({PH},{PH}) ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value", (key, str(value)))
    else: _exec(f"INSERT OR REPLACE INTO config VALUES({PH},{PH})", (key, str(value)))

# ── History ───────────────────────────────────────────────────────────────────
def _hist(op, tbl, rid, before):
    _exec(f"INSERT INTO edit_history(operation,table_name,record_id,data_before) VALUES({PH},{PH},{PH},{PH})",
          (op, tbl, rid, json.dumps(before or {}, default=str)))

def undo_last():
    last = _one("SELECT * FROM edit_history ORDER BY id DESC LIMIT 1")
    if not last: return False, "Nenhuma ação para desfazer."
    op, tbl, rid, data = last["operation"], last["table_name"], last["record_id"], json.loads(last["data_before"])
    try:
        if op == "DELETE" and data:
            cols = [k for k in data if k != "id"]; phs = ",".join([PH]*len(cols)); vals = [data[k] for k in cols]
            _exec(f"INSERT INTO {tbl}(id,{','.join(cols)}) VALUES({PH},{phs})", [rid]+vals); msg = f"Restaurado: {data.get('label', rid)}"
        elif op == "INSERT": _exec(f"DELETE FROM {tbl} WHERE id={PH}", (rid,)); msg = "Adição desfeita."
        elif op == "UPDATE" and data:
            sets = ",".join([f"{k}={PH}" for k in data if k != "id"]); vals = [data[k] for k in data if k != "id"]
            _exec(f"UPDATE {tbl} SET {sets} WHERE id={PH}", vals+[rid]); msg = f"Edição revertida: {data.get('label', rid)}"
        else: return False, "Não foi possível desfazer."
        _exec(f"DELETE FROM edit_history WHERE id={PH}", (last["id"],)); return True, msg
    except Exception as e: return False, str(e)

# ── Income ────────────────────────────────────────────────────────────────────
def get_income(month): return _fetch(f"SELECT * FROM income WHERE month={PH} ORDER BY due_day,id", (month,))
def add_income(month, label, amount, due_day=30):
    rid = _exec(f"INSERT INTO income(month,label,amount,due_day) VALUES({PH},{PH},{PH},{PH})", (month,label,amount,due_day))
    _hist("INSERT","income",rid,None)
def update_income(rid, label, amount, due_day):
    before = _one(f"SELECT * FROM income WHERE id={PH}", (rid,)); _hist("UPDATE","income",rid,before)
    _exec(f"UPDATE income SET label={PH},amount={PH},due_day={PH} WHERE id={PH}", (label,amount,due_day,rid))
def del_income(rid):
    before = _one(f"SELECT * FROM income WHERE id={PH}", (rid,)); _hist("DELETE","income",rid,before)
    _exec(f"DELETE FROM income WHERE id={PH}", (rid,))

# ── Fixed Expenses ────────────────────────────────────────────────────────────
def get_fixed(month): return _fetch(f"SELECT * FROM fixed_expenses WHERE month={PH} ORDER BY due_day,id", (month,))
def add_fixed(month, label, amount, due_day, category):
    _exec(f"INSERT INTO fixed_expenses(month,label,amount,due_day,category) VALUES({PH},{PH},{PH},{PH},{PH})", (month,label,amount,due_day,category))
def update_fixed(rid, label, amount, due_day, category):
    before = _one(f"SELECT * FROM fixed_expenses WHERE id={PH}", (rid,)); _hist("UPDATE","fixed_expenses",rid,before)
    _exec(f"UPDATE fixed_expenses SET label={PH},amount={PH},due_day={PH},category={PH} WHERE id={PH}", (label,amount,due_day,category,rid))
def del_fixed(rid):
    before = _one(f"SELECT * FROM fixed_expenses WHERE id={PH}", (rid,)); _hist("DELETE","fixed_expenses",rid,before)
    _exec(f"DELETE FROM fixed_expenses WHERE id={PH}", (rid,))
def copy_fixed_prev(month):
    y,m = int(month[:4]),int(month[5:]); m -= 1
    if m == 0: y -= 1; m = 12
    prev = f"{y}-{m:02d}"
    n = (_one(f"SELECT COUNT(*) as n FROM fixed_expenses WHERE month={PH}", (month,)) or {}).get("n",0)
    if n > 0: return 0
    rows = _fetch(f"SELECT label,amount,due_day,category FROM fixed_expenses WHERE month={PH}", (prev,))
    for r in rows: _exec(f"INSERT INTO fixed_expenses(month,label,amount,due_day,category) VALUES({PH},{PH},{PH},{PH},{PH})", (month,r["label"],r["amount"],r["due_day"],r["category"]))
    return len(rows)

# ── Credit Card ───────────────────────────────────────────────────────────────
def get_cc_all(): return _fetch("SELECT * FROM credit_card_items ORDER BY created_at DESC")
def _am(y,m,n): m+=n; y+=(m-1)//12; m=(m-1)%12+1; return y,m
def cc_total_month(month):
    ty,tm = int(month[:4]),int(month[5:])
    return sum(it["total_amount"]/it["installments"] for it in get_cc_all() for i in range(it["installments"]) if _am(int(it["start_month"][:4]),int(it["start_month"][5:]),i)==(ty,tm))
def cc_items_month(month):
    ty,tm = int(month[:4]),int(month[5:]); result=[]
    for it in get_cc_all():
        sy,sm = int(it["start_month"][:4]),int(it["start_month"][5:])
        for i in range(it["installments"]):
            if _am(sy,sm,i)==(ty,tm):
                result.append({"id":it["id"],"label":it["label"],"card":it["card_name"],"installment":f"{i+1}/{it['installments']}","monthly":it["total_amount"]/it["installments"],"total":it["total_amount"]}); break
    return result
def add_cc(label,total,installments,start_month,card_name="Cartão Principal"):
    _exec(f"INSERT INTO credit_card_items(label,total_amount,installments,start_month,card_name) VALUES({PH},{PH},{PH},{PH},{PH})", (label,total,installments,start_month,card_name))
def del_cc(rid): _exec(f"DELETE FROM credit_card_items WHERE id={PH}", (rid,))

# ── Extra Expenses ────────────────────────────────────────────────────────────
def get_extras(month, expense_type=None):
    if expense_type:
        return _fetch(f"SELECT * FROM extra_expenses WHERE month={PH} AND expense_type={PH} ORDER BY id", (month, expense_type))
    return _fetch(f"SELECT * FROM extra_expenses WHERE month={PH} ORDER BY id", (month,))

def add_extra(month, label, amount, category, method, expense_type='extra'):
    _exec(f"INSERT INTO extra_expenses(month,label,amount,category,payment_method,expense_type) VALUES({PH},{PH},{PH},{PH},{PH},{PH})", (month,label,amount,category,method,expense_type))
def del_extra(rid): _exec(f"DELETE FROM extra_expenses WHERE id={PH}", (rid,))

# ── Subscriptions ─────────────────────────────────────────────────────────────
def get_subs(): return _fetch("SELECT * FROM subscriptions ORDER BY active DESC,label")
def add_sub(label,amount,category,billing_day,notes=""):
    _exec(f"INSERT INTO subscriptions(label,amount,category,billing_day,notes) VALUES({PH},{PH},{PH},{PH},{PH})", (label,amount,category,billing_day,notes))
def toggle_sub(rid):
    cur = _one(f"SELECT active FROM subscriptions WHERE id={PH}", (rid,))
    _exec(f"UPDATE subscriptions SET active={PH} WHERE id={PH}", (0 if cur["active"] else 1, rid))
def del_sub(rid): _exec(f"DELETE FROM subscriptions WHERE id={PH}", (rid,))
def subs_total():
    r = _one("SELECT SUM(amount) as s FROM subscriptions WHERE active=1"); return float(r["s"] or 0)

# ── Debts ─────────────────────────────────────────────────────────────────────
def get_debts(): return _fetch("SELECT * FROM debts ORDER BY interest_rate DESC")
def add_debt(label,total,remaining,monthly,rate,due_day=30,notes=""):
    _exec(f"INSERT INTO debts(label,total_amount,remaining_amount,monthly_payment,interest_rate,due_day,notes) VALUES({PH},{PH},{PH},{PH},{PH},{PH},{PH})", (label,total,remaining,monthly,rate,due_day,notes))
def update_debt_remaining(rid, v): _exec(f"UPDATE debts SET remaining_amount={PH} WHERE id={PH}", (max(0,v), rid))
def update_debt_due_day(rid, due_day): _exec(f"UPDATE debts SET due_day={PH} WHERE id={PH}", (due_day, rid))
def del_debt(rid): _exec(f"DELETE FROM debts WHERE id={PH}", (rid,))
def months_to_zero(rem, mp, rate_pct):
    if mp <= 0: return 9999
    r = rate_pct/100
    if r == 0: return int(rem/mp)+1
    if mp <= rem*r: return 9999
    return math.ceil(math.log(mp/(mp-rem*r))/math.log(1+r))

# ── Investments ───────────────────────────────────────────────────────────────
def get_investments(): return _fetch("SELECT * FROM investments ORDER BY month")
def get_last_investment_total():
    invs = get_investments(); return float(invs[-1]["total_accumulated"]) if invs else 0.0
def upsert_investment(month, amount_added, total_accumulated, inv_type, source, due_day=30, notes=""):
    kw = "EXCLUDED" if USE_PG else "excluded"
    _exec(f"INSERT INTO investments(month,amount_added,total_accumulated,investment_type,investment_source,due_day,notes) VALUES({PH},{PH},{PH},{PH},{PH},{PH},{PH}) ON CONFLICT(month) DO UPDATE SET amount_added={kw}.amount_added,total_accumulated={kw}.total_accumulated,investment_type={kw}.investment_type,investment_source={kw}.investment_source,due_day={kw}.due_day,notes={kw}.notes",
          (month,amount_added,total_accumulated,inv_type,source,due_day,notes))
def investment_projection(current, monthly, annual_rate_pct, years):
    r = (annual_rate_pct/100)/12; n = years*12
    if r == 0: return current+monthly*n
    return current*(1+r)**n+monthly*((1+r)**n-1)/r
def del_investment(rid): _exec(f"DELETE FROM investments WHERE id={PH}", (rid,))

# ── Insurance ─────────────────────────────────────────────────────────────────
def get_insurance(): return _fetch("SELECT * FROM insurance ORDER BY label")
def insurance_total():
    r = _one("SELECT SUM(monthly_cost) as s FROM insurance"); return float(r["s"] or 0)
def add_insurance(label, provider, monthly_cost, coverage, due_day=30, notes=""):
    _exec(f"INSERT INTO insurance(label,provider,monthly_cost,coverage,due_day,notes) VALUES({PH},{PH},{PH},{PH},{PH},{PH})", (label,provider,monthly_cost,coverage,due_day,notes))
def update_insurance_due_day(rid, due_day): _exec(f"UPDATE insurance SET due_day={PH} WHERE id={PH}", (due_day, rid))
def del_insurance(rid): _exec(f"DELETE FROM insurance WHERE id={PH}", (rid,))

# ── Goals ─────────────────────────────────────────────────────────────────────
def get_goals(): return _fetch("SELECT * FROM goals ORDER BY deadline")
def add_goal(label, target, current=0, deadline="", notes=""):
    _exec(f"INSERT INTO goals(label,target_amount,current_amount,deadline,notes) VALUES({PH},{PH},{PH},{PH},{PH})", (label,target,current,deadline,notes))
def update_goal(rid, current): _exec(f"UPDATE goals SET current_amount={PH} WHERE id={PH}", (current, rid))
def del_goal(rid): _exec(f"DELETE FROM goals WHERE id={PH}", (rid,))

# ── Emergency Fund ────────────────────────────────────────────────────────────
def get_ef(month):
    r = _one(f"SELECT balance FROM emergency_fund WHERE month={PH}", (month,)); return float(r["balance"]) if r else 0.0
def set_ef(month, balance):
    kw = "EXCLUDED" if USE_PG else "excluded"
    _exec(f"INSERT INTO emergency_fund(month,balance) VALUES({PH},{PH}) ON CONFLICT(month) DO UPDATE SET balance={kw}.balance", (month, balance))

# ── Bills ─────────────────────────────────────────────────────────────────────
def get_bill_templates(): return _fetch("SELECT * FROM bill_templates ORDER BY due_day,label")
def get_bills(month): return _fetch(f"SELECT * FROM bills WHERE month={PH} ORDER BY due_day,label", (month,))
def add_bill_template(label, estimated, category, due_day):
    _exec(f"INSERT INTO bill_templates(label,estimated_amount,category,due_day) VALUES({PH},{PH},{PH},{PH})", (label,estimated,category,due_day))
def del_bill_template(rid): _exec(f"DELETE FROM bill_templates WHERE id={PH}", (rid,))
def generate_bills_from_templates(month):
    existing = [r["label"] for r in get_bills(month)]
    templates = _fetch("SELECT * FROM bill_templates WHERE active=1"); added = 0
    for t in templates:
        if t["label"] not in existing:
            _exec(f"INSERT INTO bills(month,label,amount,category,due_day) VALUES({PH},{PH},{PH},{PH},{PH})", (month,t["label"],t["estimated_amount"],t["category"],t["due_day"])); added += 1
    return added
def upsert_bill(month, label, amount, category, due_day):
    ex = _one(f"SELECT id FROM bills WHERE month={PH} AND label={PH}", (month, label))
    if ex: _exec(f"UPDATE bills SET amount={PH},category={PH},due_day={PH} WHERE id={PH}", (amount,category,due_day,ex["id"]))
    else: _exec(f"INSERT INTO bills(month,label,amount,category,due_day) VALUES({PH},{PH},{PH},{PH},{PH})", (month,label,amount,category,due_day))
def del_bill(rid): _exec(f"DELETE FROM bills WHERE id={PH}", (rid,))

# ── Payments ──────────────────────────────────────────────────────────────────
def get_payments(month): return _fetch(f"SELECT * FROM payments WHERE month={PH}", (month,))
def set_payment(month, itype, iid, ilabel, amount, paid: bool):
    paid_at = datetime.now().isoformat() if paid else None
    kw = "EXCLUDED" if USE_PG else "excluded"
    _exec(f"INSERT INTO payments(month,item_type,item_id,item_label,amount,paid,paid_at) VALUES({PH},{PH},{PH},{PH},{PH},{PH},{PH}) ON CONFLICT(month,item_type,item_id) DO UPDATE SET paid={kw}.paid,paid_at={kw}.paid_at",
          (month,itype,iid,ilabel,amount,1 if paid else 0,paid_at))
def is_paid(month, itype, iid):
    r = _one(f"SELECT paid FROM payments WHERE month={PH} AND item_type={PH} AND item_id={PH}", (month,itype,iid)); return bool(r and r["paid"])
