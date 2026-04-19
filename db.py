import os, json, hashlib, math
from datetime import datetime
from contextlib import contextmanager
from typing import Optional, Tuple, List

import psycopg2
from psycopg2 import pool
import psycopg2.extras

USE_PG = True 

def _get_secret(key: str, default: str = "") -> str:
    try:
        import streamlit as st
        return st.secrets.get(key, os.environ.get(key, default))
    except Exception:
        return os.environ.get(key, default)

def get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    host = _get_secret("DB_HOST", "aws-1-sa-east-1.pooler.supabase.com")
    port = int(_get_secret("DB_PORT", 5432))
    user = _get_secret("DB_USER", "postgres.mmdhywifopqkblvmuwlq")
    password = _get_secret("DB_PASSWORD", "")
    dbname = _get_secret("DB_NAME", "postgres")

    if not password:
        raise ValueError("DB_PASSWORD não encontrada nos Secrets do Streamlit!")

    return psycopg2.pool.ThreadedConnectionPool(
        minconn=2, maxconn=10,
        host=host,
        port=port,
        user=user,
        password=password,
        dbname=dbname,
        sslmode="require",
        options="-c statement_timeout=15000 -c idle_in_transaction_session_timeout=30000",
    )

@contextmanager
def _conn():
    import streamlit as st
    pool_obj: psycopg2.pool.ThreadedConnectionPool = st.session_state["_pool"]
    conn = pool_obj.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        try: conn.rollback()
        except Exception: pass
        raise
    finally:
        pool_obj.putconn(conn)

def _exec(sql: str, params: tuple = ()) -> Optional[int]:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            conn.commit()
            try:    return cur.fetchone()[0]
            except: return None

def _fetch(sql: str, params: tuple = ()) -> List[dict]:
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]

def _one(sql: str, params: tuple = ()) -> Optional[dict]:
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            r = cur.fetchone()
            return dict(r) if r else None

def hp(pwd: str) -> str:
    return hashlib.sha256(pwd.encode()).hexdigest()

def check_pwd(pwd: str) -> bool:
    r = _one("SELECT value FROM config WHERE key=%s", ("password",))
    return bool(r) and r["value"] == hp(pwd)

def change_pwd(new: str):
    _exec("INSERT INTO config(key,value) VALUES(%s,%s) ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value",
          ("password", hp(new)))

def get_api_key() -> str:
    r = _one("SELECT value FROM config WHERE key=%s", ("api_key",))
    return r["value"] if r else ""

def set_api_key(k: str):
    _exec("INSERT INTO config(key,value) VALUES(%s,%s) ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value",
          ("api_key", k))

def get_config(key: str, default: str = "") -> str:
    r = _one("SELECT value FROM config WHERE key=%s", (key,))
    return r["value"] if r else default

def set_config(key: str, value: str):
    _exec("INSERT INTO config(key,value) VALUES(%s,%s) ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value",
          (key, str(value)))

def _hist(op: str, tbl: str, rid, before):
    _exec("INSERT INTO edit_history(operation,table_name,record_id,data_before) VALUES(%s,%s,%s,%s)",
          (op, tbl, rid, json.dumps(before or {}, default=str)))

def undo_last():
    last = _one("SELECT * FROM edit_history ORDER BY id DESC LIMIT 1")
    if not last:
        return False, "Nenhuma ação para desfazer."
    op, tbl, rid, data = last["operation"], last["table_name"], last["record_id"], json.loads(last["data_before"])
    try:
        if op == "DELETE" and data:
            cols = [k for k in data if k != "id"]
            vals = [data[k] for k in cols]
            phs  = ",".join(["%s"] * len(cols))
            _exec(f"INSERT INTO {tbl}(id,{','.join(cols)}) VALUES(%s,{phs})", [rid] + vals)
            msg = f"Restaurado: {data.get('label', rid)}"
        elif op == "INSERT":
            _exec(f"DELETE FROM {tbl} WHERE id=%s", (rid,))
            msg = "Adição desfeita."
        elif op == "UPDATE" and data:
            sets = ",".join([f"{k}=%s" for k in data if k != "id"])
            vals = [data[k] for k in data if k != "id"]
            _exec(f"UPDATE {tbl} SET {sets} WHERE id=%s", vals + [rid])
            msg = f"Edição revertida: {data.get('label', rid)}"
        else:
            return False, "Não foi possível desfazer."
        _exec("DELETE FROM edit_history WHERE id=%s", (last["id"],))
        return True, msg
    except Exception as e:
        return False, str(e)

# ── PROPAGAÇÃO AUTOMÁTICA ─────────────────────────────────────────────────────
def copy_income_prev(month: str) -> int:
    y, m = int(month[:4]), int(month[5:])
    m -= 1
    if m == 0: y -= 1; m = 12
    prev = f"{y}-{m:02d}"
    rows = _fetch("SELECT label,amount,due_day FROM income WHERE month=%s", (prev,))
    for r in rows:
        _exec("INSERT INTO income(month,label,amount,due_day) VALUES(%s,%s,%s,%s)",
              (month, r["label"], r["amount"], r["due_day"]))
    return len(rows)

def copy_fixed_prev(month: str) -> int:
    y, m = int(month[:4]), int(month[5:])
    m -= 1
    if m == 0: y -= 1; m = 12
    prev = f"{y}-{m:02d}"
    rows = _fetch("SELECT label,amount,due_day,category,payment_cycle FROM fixed_expenses WHERE month=%s", (prev,))
    for r in rows:
        _exec("INSERT INTO fixed_expenses(month,label,amount,due_day,category,payment_cycle) VALUES(%s,%s,%s,%s,%s,%s)",
              (month, r["label"], r["amount"], r["due_day"], r["category"], r.get("payment_cycle")))
    return len(rows)

def get_month_data(month: str) -> dict:
    with _conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        d: dict = {}
        
        # Renda: Busca e propaga automaticamente
        cur.execute("SELECT * FROM income WHERE month=%s ORDER BY due_day,id", (month,))
        d["income"] = [dict(r) for r in cur.fetchall()]
        if not d["income"]:
            if copy_income_prev(month) > 0:
                cur.execute("SELECT * FROM income WHERE month=%s ORDER BY due_day,id", (month,))
                d["income"] = [dict(r) for r in cur.fetchall()]

        # Contas Fixas: Busca e propaga automaticamente
        cur.execute("SELECT * FROM fixed_expenses WHERE month=%s ORDER BY due_day,id", (month,))
        d["fixed"] = [dict(r) for r in cur.fetchall()]
        if not d["fixed"]:
            if copy_fixed_prev(month) > 0:
                cur.execute("SELECT * FROM fixed_expenses WHERE month=%s ORDER BY due_day,id", (month,))
                d["fixed"] = [dict(r) for r in cur.fetchall()]

        cur.execute("SELECT * FROM extra_expenses    WHERE month=%s ORDER BY id",         (month,))
        d["extras"] = [dict(r) for r in cur.fetchall()]
        cur.execute("SELECT * FROM bills             WHERE month=%s ORDER BY due_day,label", (month,))
        d["bills"] = [dict(r) for r in cur.fetchall()]
        cur.execute("SELECT * FROM payments          WHERE month=%s",                     (month,))
        d["payments"] = [dict(r) for r in cur.fetchall()]
        
        cur.execute("SELECT balance FROM emergency_fund WHERE month=%s",                  (month,))
        r = cur.fetchone()
        d["ef"] = float(r["balance"]) if r else 0.0
        
        cur.execute("SELECT * FROM subscriptions ORDER BY active DESC, label")
        d["subs"] = [dict(r) for r in cur.fetchall()]
        cur.execute("SELECT * FROM credit_card_items ORDER BY created_at DESC")
        d["cc_all"] = [dict(r) for r in cur.fetchall()]
        cur.execute("SELECT * FROM debts ORDER BY interest_rate DESC")
        d["debts"] = [dict(r) for r in cur.fetchall()]
        
        # Tabela Investments reaproveitada para "Guardado"
        cur.execute("SELECT * FROM investments ORDER BY month")
        d["investments"] = [dict(r) for r in cur.fetchall()]
        
        cur.execute("SELECT * FROM goals ORDER BY deadline")
        d["goals"] = [dict(r) for r in cur.fetchall()]
        cur.execute("SELECT * FROM bill_templates ORDER BY due_day, label")
        d["bill_templates"] = [dict(r) for r in cur.fetchall()]
        cur.execute("SELECT key, value FROM config WHERE key IN ('ef_target','inv_rate','inv_contrib','api_key')")
        d["config"] = {r["key"]: r["value"] for r in cur.fetchall()}
        cur.execute("SELECT value FROM config WHERE key=%s", ("password",))
        r = cur.fetchone()
        d["pwd_hash"] = r["value"] if r else ""
        return d

def cc_total_from_data(cc_all: list, month: str) -> float:
    ty, tm = int(month[:4]), int(month[5:])
    total = 0.0
    for it in cc_all:
        sy, sm = int(it["start_month"][:4]), int(it["start_month"][5:])
        for i in range(it["installments"]):
            ny, nm = sy, sm + i
            ny += (nm - 1) // 12
            nm = (nm - 1) % 12 + 1
            if (ny, nm) == (ty, tm):
                total += it["total_amount"] / it["installments"]
                break
    return total

def cc_items_from_data(cc_all: list, month: str) -> list:
    ty, tm = int(month[:4]), int(month[5:])
    result = []
    for it in cc_all:
        sy, sm = int(it["start_month"][:4]), int(it["start_month"][5:])
        for i in range(it["installments"]):
            ny, nm = sy, sm + i
            ny += (nm - 1) // 12
            nm = (nm - 1) % 12 + 1
            if (ny, nm) == (ty, tm):
                result.append({
                    "id": it["id"], "label": it["label"], "card": it["card_name"],
                    "installment": f"{i+1}/{it['installments']}",
                    "monthly": it["total_amount"] / it["installments"],
                    "total": it["total_amount"],
                })
                break
    return result

def is_paid_fast(payments: list, month: str, itype: str, iid: int) -> bool:
    for p in payments:
        if p["item_type"] == itype and p["item_id"] == iid:
            return bool(p["paid"])
    return False

def investment_last_total(investments: list) -> float:
    return sum(float(r["amount_added"]) for r in investments)

def months_to_zero(rem: float, mp: float, rate_pct: float) -> int:
    if mp <= 0: return 9999
    r = rate_pct / 100
    if r == 0: return int(rem / mp) + 1
    if mp <= rem * r: return 9999
    return math.ceil(math.log(mp / (mp - rem * r)) / math.log(1 + r))

def add_income(m, l, a, d=30):
    rid = _exec("INSERT INTO income(month,label,amount,due_day) VALUES(%s,%s,%s,%s) RETURNING id", (m, l, a, d))
    _hist("INSERT", "income", rid, None)
    return rid

def update_income(rid, l, a, d):
    before = _one("SELECT * FROM income WHERE id=%s", (rid,))
    _hist("UPDATE", "income", rid, before)
    _exec("UPDATE income SET label=%s,amount=%s,due_day=%s WHERE id=%s", (l, a, d, rid))

def del_income(rid):
    before = _one("SELECT * FROM income WHERE id=%s", (rid,))
    _hist("DELETE", "income", rid, before)
    _exec("DELETE FROM income WHERE id=%s", (rid,))

def add_fixed(m, l, a, d, cat):
    rid = _exec("INSERT INTO fixed_expenses(month,label,amount,due_day,category) VALUES(%s,%s,%s,%s,%s) RETURNING id",
                (m, l, a, d, cat))
    _hist("INSERT", "fixed_expenses", rid, None)
    return rid

def update_fixed(rid, l, a, d, cat):
    before = _one("SELECT * FROM fixed_expenses WHERE id=%s", (rid,))
    _hist("UPDATE", "fixed_expenses", rid, before)
    _exec("UPDATE fixed_expenses SET label=%s,amount=%s,due_day=%s,category=%s WHERE id=%s", (l, a, d, cat, rid))

def update_fixed_cycle(rid, cycle):
    _exec("UPDATE fixed_expenses SET payment_cycle=%s WHERE id=%s", (cycle, rid))

def del_fixed(rid):
    before = _one("SELECT * FROM fixed_expenses WHERE id=%s", (rid,))
    _hist("DELETE", "fixed_expenses", rid, before)
    _exec("DELETE FROM fixed_expenses WHERE id=%s", (rid,))

def add_cc(l, tot, inst, sm, cn="Cartão Principal"):
    rid = _exec("INSERT INTO credit_card_items(label,total_amount,installments,start_month,card_name) VALUES(%s,%s,%s,%s,%s) RETURNING id",
          (l, tot, inst, sm, cn))
    return rid

def del_cc(rid):
    _exec("DELETE FROM credit_card_items WHERE id=%s", (rid,))

def add_extra(m, l, a, cat, method, expense_type="extra", fund_source="Salário do Mês"):
    rid = _exec("INSERT INTO extra_expenses(month,label,amount,category,payment_method,expense_type,fund_source) VALUES(%s,%s,%s,%s,%s,%s,%s) RETURNING id",
          (m, l, a, cat, method, expense_type, fund_source))
    return rid

def del_extra(rid):
    _exec("DELETE FROM extra_expenses WHERE id=%s", (rid,))

def add_sub(l, a, cat, bd, notes=""):
    rid = _exec("INSERT INTO subscriptions(label,amount,category,billing_day,notes) VALUES(%s,%s,%s,%s,%s) RETURNING id",
          (l, a, cat, bd, notes))
    return rid

def toggle_sub(rid):
    cur = _one("SELECT active FROM subscriptions WHERE id=%s", (rid,))
    _exec("UPDATE subscriptions SET active=%s WHERE id=%s", (0 if cur["active"] else 1, rid))

def del_sub(rid):
    _exec("DELETE FROM subscriptions WHERE id=%s", (rid,))

def add_debt(l, tot, rem, mp, rate, due_day=30, notes=""):
    rid = _exec("INSERT INTO debts(label,total_amount,remaining_amount,monthly_payment,interest_rate,due_day,notes) VALUES(%s,%s,%s,%s,%s,%s,%s) RETURNING id",
          (l, tot, rem, mp, rate, due_day, notes))
    return rid

def update_debt_remaining(rid, v):
    _exec("UPDATE debts SET remaining_amount=%s WHERE id=%s", (max(0, v), rid))

def update_debt_due_day(rid, d):
    _exec("UPDATE debts SET due_day=%s WHERE id=%s", (d, rid))

def del_debt(rid):
    _exec("DELETE FROM debts WHERE id=%s", (rid,))

def add_guardado(month, a, l):
    rid = _exec("INSERT INTO investments(month,amount_added,notes) VALUES(%s,%s,%s) RETURNING id", (month, a, l))
    return rid

def del_guardado(rid):
    _exec("DELETE FROM investments WHERE id=%s", (rid,))

def add_goal(l, tg, cur=0, dl="", notes=""):
    rid = _exec("INSERT INTO goals(label,target_amount,current_amount,deadline,notes) VALUES(%s,%s,%s,%s,%s) RETURNING id",
          (l, tg, cur, dl, notes))
    return rid

def update_goal(rid, cur):
    _exec("UPDATE goals SET current_amount=%s WHERE id=%s", (cur, rid))

def del_goal(rid):
    _exec("DELETE FROM goals WHERE id=%s", (rid,))

def add_bill_template(l, est, cat, dd):
    rid = _exec("INSERT INTO bill_templates(label,estimated_amount,category,due_day) VALUES(%s,%s,%s,%s) RETURNING id",
          (l, est, cat, dd))
    return rid

def del_bill_template(rid):
    _exec("DELETE FROM bill_templates WHERE id=%s", (rid,))

def generate_bills_from_templates(month: str, bills: list, templates: list) -> int:
    existing_labels = {r["label"] for r in bills}
    added = 0
    for t in templates:
        if t["label"] not in existing_labels and t.get("active", 1):
            _exec("INSERT INTO bills(month,label,amount,category,due_day) VALUES(%s,%s,%s,%s,%s)",
                  (month, t["label"], t["estimated_amount"], t["category"], t["due_day"]))
            added += 1
    return added

def upsert_bill(month, label, amount, category, due_day):
    ex = _one("SELECT id FROM bills WHERE month=%s AND label=%s", (month, label))
    if ex:
        _exec("UPDATE bills SET amount=%s,category=%s,due_day=%s WHERE id=%s",
              (amount, category, due_day, ex["id"]))
    else:
        _exec("INSERT INTO bills(month,label,amount,category,due_day) VALUES(%s,%s,%s,%s,%s) RETURNING id",
              (month, label, amount, category, due_day))

def set_payment(month, itype, iid, ilabel, amount, paid: bool):
    paid_at = datetime.now().isoformat() if paid else None
    _exec(
        "INSERT INTO payments(month,item_type,item_id,item_label,amount,paid,paid_at) "
        "VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(month,item_type,item_id) "
        "DO UPDATE SET paid=EXCLUDED.paid, paid_at=EXCLUDED.paid_at",
        (month, itype, iid, ilabel, amount, 1 if paid else 0, paid_at),
    )

def update_sub_billing_day(rid, day):
    _exec("UPDATE subscriptions SET billing_day=%s WHERE id=%s", (day, rid))

def get_projection_data(start_month: str, periods: int = 24) -> list:
    base = get_month_data(start_month)
    projection = []
    
    curr_y = int(start_month[:4])
    curr_m = int(start_month[5:])
    
    for i in range(periods):
        m_str = f"{curr_y}-{curr_m:02d}"
        
        inc_15 = sum(r["amount"] for r in base["income"] if 11 <= r["due_day"] <= 29)
        inc_30 = sum(r["amount"] for r in base["income"] if r["due_day"] >= 30 or r["due_day"] <= 10)
        
        def get_cycle(r):
            return r.get("payment_cycle") or (15 if 11 <= r.get("due_day", 30) <= 29 else 30)
            
        fix_15 = sum(r["amount"] for r in base["fixed"] if get_cycle(r) == 15)
        fix_30 = sum(r["amount"] for r in base["fixed"] if get_cycle(r) == 30)
        
        bills_15 = sum(t["estimated_amount"] for t in base["bill_templates"] if 11 <= t["due_day"] <= 29)
        bills_30 = sum(t["estimated_amount"] for t in base["bill_templates"] if t["due_day"] >= 30 or t["due_day"] <= 10)
        
        cc_val = cc_total_from_data(base["cc_all"], m_str)
        
        debt_15 = 0
        debt_30 = 0
        for d in base["debts"]:
            meses_restantes = months_to_zero(d["remaining_amount"], d["monthly_payment"], d["interest_rate"])
            if i < meses_restantes:
                if 11 <= d.get("due_day", 30) <= 29: debt_15 += d["monthly_payment"]
                else: debt_30 += d["monthly_payment"]
        
        total_15 = fix_15 + bills_15 + debt_15
        total_30 = fix_30 + bills_30 + debt_30 + cc_val
        
        sobra_15 = inc_15 - total_15
        sobra_30 = inc_30 - total_30
        
        projection.append({
            "mes": m_str,
            "inc_15": inc_15, "gas_15": total_15, "sobra_15": sobra_15,
            "inc_30": inc_30, "gas_30": total_30, "sobra_30": sobra_30,
            "sobra_geral": sobra_15 + sobra_30
        })
        
        # Increment month safely without external libraries
        curr_m += 1
        if curr_m > 12:
            curr_m = 1
            curr_y += 1
            
    return projection


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS config(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS income(id SERIAL PRIMARY KEY, month TEXT, label TEXT, amount FLOAT DEFAULT 0, due_day INT DEFAULT 30);
CREATE TABLE IF NOT EXISTS fixed_expenses(id SERIAL PRIMARY KEY, month TEXT, label TEXT, amount FLOAT DEFAULT 0, due_day INT DEFAULT 30, category TEXT DEFAULT 'Outros', payment_cycle INT);
CREATE TABLE IF NOT EXISTS credit_card_items(id SERIAL PRIMARY KEY, label TEXT, total_amount FLOAT, installments INT DEFAULT 1, start_month TEXT, card_name TEXT DEFAULT 'Cartão Principal', created_at TIMESTAMPTZ DEFAULT NOW());
CREATE TABLE IF NOT EXISTS extra_expenses(id SERIAL PRIMARY KEY, month TEXT, label TEXT, amount FLOAT DEFAULT 0, category TEXT DEFAULT 'Outros', payment_method TEXT DEFAULT 'PIX', expense_type TEXT DEFAULT 'extra', fund_source TEXT DEFAULT 'Salário do Mês');
CREATE TABLE IF NOT EXISTS subscriptions(id SERIAL PRIMARY KEY, label TEXT, amount FLOAT DEFAULT 0, category TEXT DEFAULT 'Entretenimento', billing_day INT DEFAULT 1, active INT DEFAULT 1, notes TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS debts(id SERIAL PRIMARY KEY, label TEXT, total_amount FLOAT, remaining_amount FLOAT, monthly_payment FLOAT DEFAULT 0, interest_rate FLOAT DEFAULT 0, due_day INT DEFAULT 30, notes TEXT DEFAULT '', created_at TIMESTAMPTZ DEFAULT NOW());
CREATE TABLE IF NOT EXISTS investments(id SERIAL PRIMARY KEY, month TEXT, amount_added FLOAT DEFAULT 0, total_accumulated FLOAT DEFAULT 0, investment_type TEXT DEFAULT 'Guardado', investment_source TEXT DEFAULT 'Manual', due_day INT DEFAULT 30, notes TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS goals(id SERIAL PRIMARY KEY, label TEXT, target_amount FLOAT, current_amount FLOAT DEFAULT 0, deadline TEXT DEFAULT '', notes TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS emergency_fund(id SERIAL PRIMARY KEY, month TEXT UNIQUE, balance FLOAT DEFAULT 0);
CREATE TABLE IF NOT EXISTS bill_templates(id SERIAL PRIMARY KEY, label TEXT, estimated_amount FLOAT DEFAULT 0, category TEXT DEFAULT 'Utilidades', due_day INT DEFAULT 10, active INT DEFAULT 1);
CREATE TABLE IF NOT EXISTS bills(id SERIAL PRIMARY KEY, month TEXT, label TEXT, amount FLOAT DEFAULT 0, category TEXT DEFAULT 'Utilidades', due_day INT DEFAULT 10);
CREATE TABLE IF NOT EXISTS payments(id SERIAL PRIMARY KEY, month TEXT, item_type TEXT, item_id INT, item_label TEXT, amount FLOAT DEFAULT 0, paid INT DEFAULT 0, paid_at TEXT, UNIQUE(month, item_type, item_id));
CREATE TABLE IF NOT EXISTS edit_history(id SERIAL PRIMARY KEY, operation TEXT, table_name TEXT, record_id INT, data_before TEXT, created_at TIMESTAMPTZ DEFAULT NOW());
INSERT INTO config(key,value) VALUES('password','03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4') ON CONFLICT(key) DO NOTHING;
"""

def init_db() -> Tuple[bool, str]:
    try:
        pool_obj = get_pool()
        conn = pool_obj.getconn()
        try:
            cur = conn.cursor()
            for stmt in SCHEMA_SQL.strip().split(";"):
                stmt = stmt.strip()
                if stmt and not stmt.startswith("--"):
                    try:
                        cur.execute(stmt)
                        conn.commit()
                    except Exception:
                        conn.rollback()
            
            try:
                cur.execute("ALTER TABLE extra_expenses ADD COLUMN fund_source TEXT DEFAULT 'Salário do Mês';")
                conn.commit()
            except Exception: conn.rollback()
            
            try:
                cur.execute("ALTER TABLE fixed_expenses ADD COLUMN payment_cycle INT;")
                conn.commit()
            except Exception: conn.rollback()
            
            import streamlit as st
            st.session_state["_pool"] = pool_obj
        finally:
            pool_obj.putconn(conn)
        return True, ""
    except Exception as e:
        return False, str(e)
