import os, json, hashlib
import streamlit as st
from datetime import datetime
import plotly.graph_objects as go

import db

st.set_page_config(page_title="Finanças Família", page_icon="💚",
                   layout="wide", initial_sidebar_state="expanded")

MN   = {"01":"Janeiro","02":"Fevereiro","03":"Março","04":"Abril","05":"Maio",
        "06":"Junho","07":"Julho","08":"Agosto","09":"Setembro","10":"Outubro",
        "11":"Novembro","12":"Dezembro"}
CATS = ["Moradia", "Água", "Luz", "Telefone/Internet", "Condomínio", "IPTU", 
        "Transporte", "Saúde", "Seguro de Vida", "Educação (Isa)", "Supermercado", 
        "Art Pão", "Pizza", "Compra Shopping", "IFOOD/99FOOD", "Lanches avulsos", 
        "Farmácia",  "Lazer", "Streaming", "Serviços", "Vestuário", "Outros"]
PAY  = ["PIX","Dinheiro","Débito","Transferência","Outro"]

def R(v):
    return f"R$ {v:,.2f}".replace(",","X").replace(".",",").replace("X",".")

def ML(m):
    return f"{MN.get(m[5:],'?')} {m[:4]}"

def prev_m(m):
    y,mo=int(m[:4]),int(m[5:]); mo-=1
    if mo==0: y-=1; mo=12
    return f"{y}-{mo:02d}"

def next_m(m):
    y,mo=int(m[:4]),int(m[5:]); mo+=1
    if mo==13: y+=1; mo=1
    return f"{y}-{mo:02d}"

def prog_bar(pct, color="#00c896"):
    pct=min(100,max(0,pct))
    return (f'<div style="background:#e5e7eb;border-radius:50px;height:8px;overflow:hidden;margin:6px 0">'
            f'<div style="height:8px;border-radius:50px;background:{color};width:{pct}%"></div></div>')

def _auth_token():
    week=datetime.now().strftime("%Y%W")
    pwd=db.get_config("password","")
    return hashlib.sha256(f"{pwd}{week}".encode()).hexdigest()[:24]

def _check_token(t):
    return t==_auth_token()

# ══════════════════════════════════════════════════════════════════════════════
# LOCAL STATE ENGINE (OPTIMISTIC UI - ZERO LATENCY)
# ══════════════════════════════════════════════════════════════════════════════
class LocalState:
    @staticmethod
    def get(month):
        if "mem_data" not in st.session_state or st.session_state.get("mem_month") != month:
            st.session_state.mem_data = db.get_month_data(month)
            st.session_state.mem_month = month
        return st.session_state.mem_data

    @staticmethod
    def get_leftover(month):
        d = db.get_month_data(month)
        t_inc = sum(r["amount"] for r in d["income"])
        cc = db.cc_total_from_data(d["cc_all"], month)
        
        # Considera apenas os extras que saíram do salário do mês
        ext_do_mes = sum(r["amount"] for r in d["extras"] if r.get("fund_source", "Salário do Mês") == "Salário do Mês")
        
        t_gas = sum(r["amount"] for r in d["fixed"]) + cc + ext_do_mes + \
                sum(r["amount"] for r in d["subs"] if r["active"]) + \
                sum(r["amount"] for r in d["bills"])
        t_debt = sum(r["monthly_payment"] for r in d["debts"])
        return t_inc - t_gas - t_debt

    @staticmethod
    def reload():
        st.session_state.pop("mem_data", None)
        st.rerun()

    @staticmethod
    def remove(table, rid):
        d = st.session_state.mem_data
        if table in d:
            d[table] = [x for x in d[table] if x["id"] != rid]
        st.rerun()

    @staticmethod
    def add(table, record):
        st.session_state.mem_data[table].append(record)
        st.rerun()

    @staticmethod
    def update(table, rid, **kwargs):
        for row in st.session_state.mem_data[table]:
            if row["id"] == rid:
                row.update(kwargs)
                break
        st.rerun()

    @staticmethod
    def toggle_payment(month, itype, iid, amount, paid):
        d = st.session_state.mem_data
        db.set_payment(month, itype, iid, "", amount, paid)
        found = False
        for p in d["payments"]:
            if p["item_type"] == itype and p["item_id"] == iid:
                p["paid"] = 1 if paid else 0
                found = True
                break
        if not found:
            d["payments"].append({"month": month, "item_type": itype, "item_id": iid, "amount": amount, "paid": 1 if paid else 0})
        st.rerun()

# ── CSS ───────────────────────────────────────────────────────────────────────
CSS = """<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=DM+Mono:wght@400;500&display=swap');
:root{--green:#00c896;--green2:#00a67e;--navy:#1a2332;--body:#374151;--muted:#6b7280;--border:#e5e7eb;--surface:#f9fafb;--white:#ffffff;--red:#ef4444;--amber:#f59e0b;--blue:#3b82f6;}
*,*::before,*::after{box-sizing:border-box}
html,body,.stApp{background:var(--white)!important;color:var(--body)!important;font-family:'Inter',sans-serif!important}
[data-testid="stSidebar"]{background:#f8fafc!important;border-right:1px solid var(--border)!important}
[data-testid="stSidebar"] *{font-family:'Inter',sans-serif!important}
#MainMenu,footer,header,.stDeployButton{visibility:hidden!important}
.block-container{padding-top:.8rem!important;max-width:1300px}
[data-testid="collapsedControl"],[data-testid="stSidebarCollapseButton"],button[data-testid="baseButton-header"]{display:none!important}
.stTabs [data-baseweb="tab-list"]{gap:0;border-bottom:2px solid var(--border);background:transparent;padding:0;overflow-x:auto}
.stTabs [data-baseweb="tab"]{background:transparent!important;color:var(--muted)!important;font-family:'Inter',sans-serif!important;font-size:13px!important;font-weight:500!important;padding:10px 16px!important;border-radius:0!important;border-bottom:2px solid transparent!important;margin-bottom:-2px;white-space:nowrap}
.stTabs [aria-selected="true"]{color:var(--green2)!important;border-bottom:2px solid var(--green)!important}
.stTabs [data-baseweb="tab-highlight"],.stTabs [data-baseweb="tab-border"]{display:none!important}
.card{background:var(--white);border:1px solid var(--border);border-radius:12px;padding:18px 20px;margin-bottom:12px}
.card-green{border-left:3px solid var(--green)}.card-red{border-left:3px solid var(--red)}.card-amber{border-left:3px solid var(--amber)}.card-blue{border-left:3px solid var(--blue)}.card-purple{border-left:3px solid #8b5cf6}
.mc{background:var(--white);border:1px solid var(--border);border-radius:12px;padding:14px 16px;text-align:center}
.mc-val{font-size:20px;font-weight:700;font-family:'DM Mono',monospace;line-height:1.1;margin-bottom:3px}
.mc-label{font-size:10px;text-transform:uppercase;letter-spacing:1.5px;color:var(--muted);font-weight:500}
.tbl{width:100%;border-collapse:collapse;font-size:13px}
.tbl thead tr{background:var(--green);color:white}.tbl thead th{padding:8px 12px;text-align:left;font-weight:600;font-size:12px}
.tbl tbody tr{border-bottom:1px solid var(--border)}.tbl tbody tr:hover{background:#f0fdf9}.tbl tbody td{padding:7px 12px}
.tbl tfoot tr{background:var(--surface);border-top:2px solid var(--border);font-weight:700}.tbl tfoot td{padding:8px 12px}
.sec{font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:2px;color:var(--green2);margin-bottom:12px;padding-bottom:8px;border-bottom:1px solid var(--border)}
.badge{display:inline-block;padding:2px 8px;border-radius:50px;font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.5px}
.b-green{background:#dcfce7;color:#16a34a}.b-red{background:#fee2e2;color:#dc2626}.b-amber{background:#fef3c7;color:#d97706}.b-blue{background:#dbeafe;color:#2563eb}.b-gray{background:#f3f4f6;color:#6b7280}.b-15{background:#dbeafe;color:#1d4ed8}.b-30{background:#ede9fe;color:#7c3aed}
.stTextInput>div>div{border:1.5px solid var(--border)!important;border-radius:8px!important;background:var(--white)!important}
.stTextInput input{color:var(--body)!important;background:var(--white)!important;font-size:14px!important}
.stNumberInput>div>div{border:1.5px solid var(--border)!important;border-radius:8px!important;background:var(--white)!important}
.stSelectbox>div>div{border:1px solid var(--border)!important;border-radius:8px!important;background:var(--white)!important;font-size:13px!important}
label{color:var(--body)!important;font-size:12px!important;font-weight:500!important}
.stButton>button{background:var(--green)!important;color:white!important;border:none!important;border-radius:8px!important;font-weight:600!important;font-size:13px!important;padding:6px 18px!important}
.stButton>button:hover{background:var(--green2)!important}
.stFormSubmitButton>button{background:var(--green)!important;color:white!important;border:none!important;border-radius:8px!important;font-weight:600!important;font-size:13px!important;width:100%}
::-webkit-scrollbar{width:5px}::-webkit-scrollbar-thumb{background:#d1d5db;border-radius:3px}
.diag-ok{background:#f0fdf4;border:1px solid #bbf7d0;border-radius:10px;padding:12px 16px;color:#166534;font-size:14px;margin-bottom:16px}
.diag-warn{background:#fffbeb;border:1px solid #fde68a;border-radius:10px;padding:12px 16px;color:#92400e;font-size:14px;margin-bottom:16px}
.diag-crit{background:#fef2f2;border:1px solid #fecaca;border-radius:10px;padding:12px 16px;color:#991b1b;font-size:14px;margin-bottom:16px}
.diag-info{background:#eff6ff;border:1px solid #bfdbfe;border-radius:10px;padding:12px 16px;color:#1e40af;font-size:14px;margin-bottom:16px}
</style>"""

def login_page():
    _, col, _ = st.columns([1,1.2,1])
    with col:
        st.markdown("""<div style="text-align:center;padding:48px 0 28px">
          <div style="display:flex;align-items:center;justify-content:center;gap:12px;margin-bottom:18px">
            <div style="width:50px;height:50px;border-radius:50%;border:3px solid #00c896;display:flex;align-items:center;justify-content:center;font-size:22px">💚</div>
            <span style="font-size:24px;font-weight:700;color:#1a2332">minhas<span style="color:#00c896">Finanças</span></span>
          </div>
          <h2 style="font-size:26px;font-weight:700;color:#1a2332;margin:0">Oi, Família Peixoto!</h2>
          <p style="color:#6b7280;font-size:13px;margin-top:6px">Controle financeiro da família</p>
        </div>""", unsafe_allow_html=True)
        pwd = st.text_input("Senha de acesso", type="password", placeholder="Digite sua senha...")
        lembre = st.checkbox("Continuar logado neste navegador", value=True)
        if st.button("Entrar →", width="stretch"):
            secret_hash = ""
            try: secret_hash = st.secrets.get("PASSWORD_HASH","")
            except Exception: pass
            ok = (db.hp(pwd) == secret_hash) if secret_hash else db.check_pwd(pwd)
            if ok:
                st.session_state.auth = True
                if lembre:
                    try: st.query_params["t"] = _auth_token()
                    except Exception: pass
                st.rerun()
            else:
                st.error("Senha incorreta.")

def sidebar(month):
    with st.sidebar:
        st.markdown("""<div style="display:flex;align-items:center;gap:8px;padding:16px 14px 10px">
          <div style="width:30px;height:30px;border-radius:50%;border:2px solid #00c896;display:flex;align-items:center;justify-content:center;font-size:13px">💚</div>
          <span style="font-size:15px;font-weight:700;color:#1a2332">minhas<span style="color:#00c896">Finanças</span></span>
        </div>""", unsafe_allow_html=True)
        st.divider()
        st.markdown('<div style="padding:0 4px"><div class="sec" style="margin-bottom:8px">Competência</div>', unsafe_allow_html=True)
        c1,c2,c3 = st.columns([1,3,1])
        with c1:
            if st.button("◀", key="p"):
                st.session_state.month = prev_m(month); st.rerun()
        with c2:
            st.markdown(f'<div style="text-align:center;padding:6px 0;font-size:14px;font-weight:600;color:#1a2332">{ML(month)}</div>', unsafe_allow_html=True)
        with c3:
            if st.button("▶", key="n"):
                st.session_state.month = next_m(month); st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
        st.divider()
        if st.button("↩ Desfazer última ação", width="stretch"):
            ok, msg = db.undo_last()
            (st.success if ok else st.warning)(msg)
            LocalState.reload()
        st.divider()
        st.markdown('<div style="font-size:10px;color:#16a34a;text-align:center;padding:2px 0">🚀 Optimistic UI + Auto Propagação</div>', unsafe_allow_html=True)
        st.divider()
        if st.button("↪ Sair", width="stretch"):
            st.session_state.auth = False
            try: st.query_params.clear()
            except Exception: pass
            st.rerun()
    return st.session_state.month

# ══════════════════════════════════════════════════════════════════════════════
# ABAS
# ══════════════════════════════════════════════════════════════════════════════

def tab_painel(month, d):
    inc   = d["income"]; fix   = d["fixed"]; ext   = d["extras"]; subs  = d["subs"]
    debts = d["debts"]; bills = d["bills"]
    cc_all= d["cc_all"]

    cc       = db.cc_total_from_data(cc_all, month)
    t_inc  = sum(r["amount"] for r in inc)
    t_fix  = sum(r["amount"] for r in fix)
    
    # Separação dos Gastos Extras (Mês x Porquinho)
    t_ext_mes = sum(r["amount"] for r in ext if r.get("fund_source", "Salário do Mês") == "Salário do Mês")
    t_ext_porquinho = sum(r["amount"] for r in ext if r.get("fund_source") == "Porquinho")
    t_ext = t_ext_mes + t_ext_porquinho
    
    t_subs = sum(r["amount"] for r in subs if r["active"])
    t_bills= sum(r["amount"] for r in bills)
    t_debt = sum(r["monthly_payment"] for r in debts)
    
    # O gasto mensal passa a considerar apenas o que sai do salário do mês
    t_gasto= t_fix + cc + t_ext_mes + t_subs + t_bills
    sobra  = t_inc - t_gasto - t_debt

    # Helper para descobrir o ciclo (respeita a escolha manual ou deriva do dia)
    def get_cycle(r):
        return r.get("payment_cycle") or (15 if 11 <= r.get("due_day", 30) <= 29 else 30)

    # ── Cálculos: Ciclo 15
    inc_15 = sum(r["amount"] for r in inc if 11 <= r["due_day"] <= 29)
    gas_15 = sum(r["amount"] for r in fix if get_cycle(r) == 15) + \
             sum(r["amount"] for r in bills if 11 <= r["due_day"] <= 29) + \
             sum(r["amount"] for r in subs if r["active"] and 11 <= r["billing_day"] <= 29) + \
             sum(r["monthly_payment"] for r in debts if 11 <= r.get("due_day", 30) <= 29)
    sobra_15 = inc_15 - gas_15

    # ── Cálculos: Ciclo 30
    inc_30 = sum(r["amount"] for r in inc if r["due_day"] >= 30 or r["due_day"] <= 10)
    gas_30 = sum(r["amount"] for r in fix if get_cycle(r) == 30) + \
             sum(r["amount"] for r in bills if r["due_day"] >= 30 or r["due_day"] <= 10) + \
             sum(r["amount"] for r in subs if r["active"] and (r["billing_day"] >= 30 or r["billing_day"] <= 10)) + \
             sum(r["monthly_payment"] for r in debts if (r.get("due_day", 30) >= 30 or r.get("due_day", 30) <= 10)) + \
             cc
    sobra_30 = inc_30 - gas_30

    # ── Guardado / Porquinho
    prev_leftover = LocalState.get_leftover(prev_m(month))
    man_saved = sum(float(r["amount_added"]) for r in d["investments"] if r["month"]==month)
    # Deduz o que foi gasto tirando do porquinho
    total_guardado_mes = man_saved + (prev_leftover if prev_leftover > 0 else 0) - t_ext_porquinho

    cor = "#16a34a" if sobra >= 0 else "#ef4444"
    cor15 = "#16a34a" if sobra_15 >= 0 else "#ef4444"
    cor30 = "#16a34a" if sobra_30 >= 0 else "#ef4444"

    st.markdown(f"""<div style="display:flex;align-items:center;justify-content:space-between;padding:6px 0 10px">
      <div><h1 style="font-size:26px;font-weight:700;color:#1a2332;margin:0">Painel Executivo</h1>
      <p style="color:#6b7280;font-size:13px;margin-top:3px">Resumo de {ML(month)}</p></div>
    </div>""", unsafe_allow_html=True)

    # ── DIAGNÓSTICO RÁPIDO ───────────────────────────────────────────────────
    diag_msg = ""
    if t_inc == 0:
        diag_msg = '<div class="diag-info">ℹ️ <b>Mês Novo:</b> Adicione as Rendas Esperadas para ver o diagnóstico completo da família.</div>'
    elif sobra < 0:
        diag_msg = f'<div class="diag-crit">🚨 <b>Atenção Família!</b> Vocês estão {R(abs(sobra))} no vermelho. Deem uma freada urgente, principalmente nos Gastos Extras (já foram {R(t_ext)}). O foco agora é pagar apenas o essencial!</div>'
    elif sobra > 0:
        if t_debt > 0:
            if t_ext > sobra:
                diag_msg = f'<div class="diag-warn">🟡 <b>Cuidado Priscila e Thiago:</b> Ainda tem {R(sobra)} sobrando, mas os gastos extras ({R(t_ext)}) já estão maiores que a sobra. Segurem a mão para garantir que dê para pagar as dívidas do mês!</div>'
            else:
                diag_msg = f'<div class="diag-ok">🟢 <b>Excelente mês!</b> Contas sob controle e ainda sobram {R(sobra)}. Que tal pegar uns R$ 100 para um hambúrguer a dois para celebrar, e usar o resto para adiantar as dívidas? Vocês chegam lá!</div>'
        else:
            diag_msg = f'<div class="diag-ok">🌟 <b>Cenário Ideal!</b> Sem dívidas mensais cadastradas e com {R(sobra)} livres. Vocês estão voando. Excelente mês para engordar o Porquinho da Isa ou focar nos objetivos!</div>'
    else:
         diag_msg = '<div class="diag-warn">🟡 <b>No Limite!</b> O orçamento deste mês está empatado (zero a zero). Evitem qualquer gasto extra daqui para frente para não entrar no vermelho.</div>'
    
    st.markdown(diag_msg, unsafe_allow_html=True)
    # ─────────────────────────────────────────────────────────────────────────

    c1, c2, c3 = st.columns([1,1,1.1], gap="medium")

    with c1:
        st.markdown(f'''
        <div class="card" style="border-top: 3px solid #3b82f6; padding: 20px;">
            <div class="sec" style="font-size:13px; margin-bottom: 6px;">Ciclo Dia 15</div>
            <div style="font-size:11px; color:#6b7280; margin-bottom:14px">Paga contas vencendo dia 11 a 29</div>
            <div style="display:flex; justify-content:space-between; margin-bottom:8px; font-size:14px"><span>Renda</span><span style="color:#16a34a; font-family:DM Mono,monospace">{R(inc_15)}</span></div>
            <div style="display:flex; justify-content:space-between; margin-bottom:12px; font-size:14px"><span>Saídas</span><span style="color:#ef4444; font-family:DM Mono,monospace">{R(gas_15)}</span></div>
            <div style="border-top: 1px dashed var(--border); padding-top:12px; display:flex; justify-content:space-between; font-weight:700; font-size:15px"><span>Saldo do Ciclo</span><span style="color:{cor15}; font-family:DM Mono,monospace">{R(sobra_15)}</span></div>
        </div>
        ''', unsafe_allow_html=True)
        
    with c2:
        st.markdown(f'''
        <div class="card" style="border-top: 3px solid #8b5cf6; padding: 20px;">
            <div class="sec" style="font-size:13px; margin-bottom: 6px;">Ciclo Dia 30</div>
            <div style="font-size:11px; color:#6b7280; margin-bottom:14px">Paga contas vencendo dia 30 a 10</div>
            <div style="display:flex; justify-content:space-between; margin-bottom:8px; font-size:14px"><span>Renda</span><span style="color:#16a34a; font-family:DM Mono,monospace">{R(inc_30)}</span></div>
            <div style="display:flex; justify-content:space-between; margin-bottom:12px; font-size:14px"><span>Saídas</span><span style="color:#ef4444; font-family:DM Mono,monospace">{R(gas_30)}</span></div>
            <div style="border-top: 1px dashed var(--border); padding-top:12px; display:flex; justify-content:space-between; font-weight:700; font-size:15px"><span>Saldo do Ciclo</span><span style="color:{cor30}; font-family:DM Mono,monospace">{R(sobra_30)}</span></div>
        </div>
        ''', unsafe_allow_html=True)

    with c3:
        st.markdown(f'''
        <div class="card" style="border-top: 3px solid #16a34a; background: #f8fafc; padding: 20px;">
            <div class="sec" style="font-size:13px; margin-bottom: 6px;">Total do Mês</div>
            <div style="font-size:11px; color:#6b7280; margin-bottom:14px">Geral + Guardado + Extras</div>
            <div style="display:flex; justify-content:space-between; margin-bottom:6px; font-size:14px"><span>Renda Esperada</span><span style="color:#16a34a; font-weight:600; font-family:DM Mono,monospace">{R(t_inc)}</span></div>
            <div style="display:flex; justify-content:space-between; margin-bottom:6px; font-size:14px"><span>Total Saídas</span><span style="color:#ef4444; font-weight:600; font-family:DM Mono,monospace">{R(t_gasto + t_debt)}</span></div>
            <div style="display:flex; justify-content:space-between; margin-bottom:12px; font-size:14px"><span>Sobra Acumulada</span><span style="color:#3b82f6; font-weight:600; font-family:DM Mono,monospace">{R(total_guardado_mes)}</span></div>
            <div style="border-top: 1px solid #cbd5e1; padding-top:12px; display:flex; justify-content:space-between; font-weight:800; font-size:16px"><span>Saldo Final (Mês)</span><span style="color:{cor}; font-family:DM Mono,monospace">{R(sobra)}</span></div>
        </div>
        ''', unsafe_allow_html=True)

    st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)

    from collections import defaultdict
    cat_t = defaultdict(float)
    for r in fix:   cat_t[r["category"]] += r["amount"]
    for r in ext:   cat_t[r["category"]] += r["amount"]
    for r in bills: cat_t["Contas"]       += r["amount"]
    for r in subs:
        if r["active"]: cat_t["Assinaturas"] += r["amount"]
    if cc>0:   cat_t["Cartão"]      += cc
    
    left, right = st.columns([1, 1])
    with left:
        if cat_t:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown('<div class="sec">Composição de Gastos</div>', unsafe_allow_html=True)
            cp=["#00c896","#3b82f6","#f59e0b","#ef4444","#8b5cf6","#06b6d4","#ec4899","#84cc16","#f97316","#6b7280"]
            lp,vp=list(cat_t.keys()),list(cat_t.values())
            fig=go.Figure(go.Pie(labels=lp,values=vp,hole=0.6,marker_colors=cp[:len(lp)],textinfo="label+percent",textfont_size=11,hovertemplate="%{label}: R$ %{value:,.2f}<extra></extra>"))
            fig.update_layout(height=280,margin=dict(t=5,b=5,l=0,r=0),paper_bgcolor="white",showlegend=False,font_family="Inter")
            st.plotly_chart(fig, width="stretch", config={"displayModeBar":False})
            st.markdown('</div>', unsafe_allow_html=True)
    with right:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="sec">Resumo de Saídas do Mês</div>', unsafe_allow_html=True)
        for label,value,color in [("🏠 Fixos e Contas",t_fix+t_bills,"#ef4444"),("💳 Cartão",cc,"#f59e0b"),("📤 Extras (Variáveis)",t_ext,"#6b7280"),("📱 Assinaturas",t_subs,"#8b5cf6"),("⚠️ Dívidas",t_debt,"#dc2626")]:
            if value>0:
                st.markdown(f'<div style="display:flex;justify-content:space-between;padding:12px 0;font-size:14px;border-bottom:1px dashed var(--border)"><span>{label}</span><span style="font-family:DM Mono,monospace;color:{color};font-weight:600">{R(value)}</span></div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

def tab_renda(month, d):
    inc = d["income"]
    t_inc = sum(r["amount"] for r in inc)
    st.markdown(f'<div style="display:flex;justify-content:space-between;align-items:center;padding:6px 0 14px"><div><h2 style="font-size:20px;font-weight:700;color:#1a2332;margin:0">Renda Esperada</h2><p style="color:#6b7280;font-size:12px;margin:3px 0 0">Propagada automaticamente para os próximos meses</p></div><div style="font-size:20px;font-weight:700;color:#16a34a;font-family:DM Mono,monospace">{R(t_inc)}</div></div>', unsafe_allow_html=True)
    left, right = st.columns([1.2, 1], gap="medium")
    with left:
        st.markdown('<div class="card card-green">', unsafe_allow_html=True)
        st.markdown(f'<div class="sec">Entradas de {ML(month)}</div>', unsafe_allow_html=True)
        if inc:
            for due in [15, 30]:
                sub = [r for r in inc if r["due_day"]==due]
                if not sub: continue
                st.markdown(f'<div style="margin:4px 0 4px"><span class="badge b-{15 if due==15 else 30}">Dia {due}</span></div>', unsafe_allow_html=True)
                for r in sub:
                    c1,c2,c3,c4 = st.columns([3,2,1,1])
                    c1.markdown(f'<span style="font-size:13px">{r["label"]}</span>', unsafe_allow_html=True)
                    c2.markdown(f'<span style="font-family:DM Mono,monospace;color:#16a34a;font-size:13px">{R(r["amount"])}</span>', unsafe_allow_html=True)
                    if c3.button("✎", key=f"ei{r['id']}"):   st.session_state[f"ei{r['id']}"]=True
                    if c4.button("✕", key=f"di{r['id']}"):
                        db.del_income(r["id"]); LocalState.remove("income", r["id"])
                    if st.session_state.get(f"ei{r['id']}"):
                        with st.form(f"eif{r['id']}"):
                            nl=st.text_input("Descrição",r["label"]); na=st.number_input("Valor",value=float(r["amount"]),step=10.)
                            nd=st.selectbox("Dia",[15,30],index=0 if r["due_day"]==15 else 1)
                            if st.form_submit_button("Salvar", width="stretch"):
                                db.update_income(r["id"],nl,na,nd)
                                LocalState.update("income", r["id"], label=nl, amount=na, due_day=nd)
                                del st.session_state[f"ei{r['id']}"]; st.rerun()
            st.markdown(f'<div style="display:flex;justify-content:space-between;padding:8px 0 0;border-top:1px solid var(--border);font-size:13px;font-weight:600"><span>Total</span><span style="color:#16a34a;font-family:DM Mono,monospace">{R(t_inc)}</span></div>', unsafe_allow_html=True)
        else:
            st.markdown('<p style="color:#6b7280;font-size:13px">Nenhuma renda cadastrada.</p>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    with right:
        st.markdown('<div class="card card-green">', unsafe_allow_html=True)
        st.markdown('<div class="sec">+ Adicionar Entrada</div>', unsafe_allow_html=True)
        with st.form("add_inc"):
            l=st.text_input("Descrição","",placeholder="Ex: Salário Thiago…"); a=st.number_input("Valor (R$)",min_value=0.,step=100.); d_=st.selectbox("Dia (Ciclo)",[15,30])
            if st.form_submit_button("Adicionar", width="stretch"):
                if l and a>0: 
                    rid = db.add_income(month,l,a,d_)
                    LocalState.add("income", {"id":rid, "month":month, "label":l, "amount":a, "due_day":d_})
        st.markdown('</div>', unsafe_allow_html=True)

def tab_contas(month, d):
    fix = d["fixed"]
    t_fix = sum(r["amount"] for r in fix)
    
    bills = d["bills"]
    templates = d["bill_templates"]
    if db.generate_bills_from_templates(month, bills, templates) > 0:
        LocalState.reload()
    t_bills = sum(r["amount"] for r in bills)
    pays = d["payments"]
    
    st.markdown(f'<div style="display:flex;justify-content:space-between;align-items:center;padding:6px 0 14px"><div><h2 style="font-size:20px;font-weight:700;color:#1a2332;margin:0">Contas Fixas</h2><p style="color:#6b7280;font-size:12px;margin:3px 0 0">Propagadas para todos os meses</p></div><div style="font-size:20px;font-weight:700;color:#ef4444;font-family:DM Mono,monospace">{R(t_fix + t_bills)}</div></div>', unsafe_allow_html=True)
    left,right=st.columns([1.3,1],gap="medium")
    
    with left:
        st.markdown('<div class="card card-red">', unsafe_allow_html=True)
        st.markdown('<div class="sec">Suas Contas Fixas (Sempre iguais)</div>', unsafe_allow_html=True)
        if fix:
            for r in sorted(fix, key=lambda x: x["due_day"]):
                # Deriva o ciclo atual
                current_cycle = r.get("payment_cycle") or (15 if 11 <= r["due_day"] <= 29 else 30)
                other_cycle = 30 if current_cycle == 15 else 15
                
                c1,c2,c3,c4,c5 = st.columns([3,2,0.8,0.8,0.8])
                c1.markdown(f'<div style="font-size:13px;font-weight:500">{r["label"]}</div><span class="badge b-{"15" if current_cycle==15 else "30"}" style="font-size:9px">{r["category"]} · Ciclo {current_cycle}</span>', unsafe_allow_html=True)
                c2.markdown(f'<span style="font-family:DM Mono,monospace;color:#ef4444;font-size:13px;padding-top:4px;display:block">{R(r["amount"])}</span>', unsafe_allow_html=True)
                
                # Botão para mover ciclo
                if c3.button(f"→{other_cycle}", key=f"mc_{r['id']}", help=f"Mover para Ciclo {other_cycle}"):
                    db.update_fixed_cycle(r["id"], other_cycle)
                    LocalState.update("fixed", r["id"], payment_cycle=other_cycle)

                if c4.button("✎",key=f"ef_{r['id']}"): st.session_state[f"ef_{r['id']}"]=True
                if c5.button("✕",key=f"df_{r['id']}"): 
                    db.del_fixed(r["id"]); LocalState.remove("fixed", r["id"])
                    
                if st.session_state.get(f"ef_{r['id']}"):
                    with st.form(f"eff_{r['id']}"):
                        nl=st.text_input("Descrição",r["label"]); na=st.number_input("Valor",value=float(r["amount"]),step=5.)
                        nd=st.number_input("Dia",min_value=1,max_value=31,value=r["due_day"])
                        nc=st.selectbox("Categoria",CATS,index=CATS.index(r["category"]) if r["category"] in CATS else 0)
                        if st.form_submit_button("Salvar", width="stretch"):
                            db.update_fixed(r["id"],nl,na,nd,nc)
                            LocalState.update("fixed", r["id"], label=nl, amount=na, due_day=nd, category=nc)
                            del st.session_state[f"ef_{r['id']}"]; st.rerun()
        else:
            st.markdown('<p style="color:#6b7280;font-size:13px">Nenhuma conta fixa.</p>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown(f'<div class="sec">Contas Variáveis (Água, Luz) - Mês {ML(month)}</div>', unsafe_allow_html=True)
        if bills:
            for r in bills:
                paid=db.is_paid_fast(pays,month,"bill",r["id"])
                c1,c2,c3,c4=st.columns([2.5,1.8,1,0.8])
                c1.markdown(f'<div style="padding-top:4px;font-size:13px;{"text-decoration:line-through;color:#9ca3af" if paid else ""}"><b>{r["label"]}</b><br><span class="badge b-gray" style="font-size:9px">{r["category"]} · dia {r["due_day"]}</span></div>', unsafe_allow_html=True)
                nv=c2.number_input("",value=float(r["amount"]),step=1.,key=f"bv{r['id']}",label_visibility="collapsed")
                if c3.button("💾",key=f"bs{r['id']}"):
                    db.upsert_bill(month,r["label"],nv,r["category"],r["due_day"])
                    LocalState.update("bills", r["id"], amount=nv)
                if c4.button("✅" if paid else "⬜",key=f"bp{r['id']}"):
                    LocalState.toggle_payment(month, "bill", r["id"], r["amount"], not paid)
        else:
            st.markdown('<p style="color:#6b7280;font-size:13px">Nenhuma conta variável.</p>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with right:
        st.markdown('<div class="card card-red">', unsafe_allow_html=True)
        st.markdown('<div class="sec">+ Adicionar Conta Fixa</div>', unsafe_allow_html=True)
        with st.form("add_fix"):
            l=st.text_input("Descrição","",placeholder="Ex: Aluguel…"); a=st.number_input("Valor",min_value=0.,step=10.)
            d_=st.number_input("Dia de Venc.", min_value=1, max_value=31, value=15); ca=st.selectbox("Categoria",CATS)
            if st.form_submit_button("Adicionar", width="stretch"):
                if l and a>0: 
                    rid = db.add_fixed(month,l,a,int(d_),ca)
                    LocalState.add("fixed", {"id":rid, "month":month, "label":l, "amount":a, "due_day":int(d_), "category":ca})
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="sec">Criar Modelo (Conta que varia o valor)</div>', unsafe_allow_html=True)
        with st.form("add_tpl"):
            l=st.text_input("Nome","",placeholder="Ex: Conta de Luz"); a=st.number_input("Estimativa (R$)",min_value=0.,step=5.)
            ca=st.selectbox("Categoria",CATS)
            dd=st.number_input("Dia de Venc.",min_value=1,max_value=31,value=10)
            if st.form_submit_button("Criar", width="stretch"):
                if l: 
                    rid = db.add_bill_template(l,a,ca,int(dd))
                    LocalState.add("bill_templates", {"id":rid, "label":l, "estimated_amount":a, "category":ca, "due_day":int(dd), "active":1})
        st.markdown('</div>', unsafe_allow_html=True)
        
        if templates:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown('<div class="sec">Modelos Ativos</div>', unsafe_allow_html=True)
            for t in templates:
                c1,c2,c3=st.columns([3,2,1])
                c1.markdown(f'<span style="font-size:13px">{t["label"]}</span><br><span class="badge b-gray">{t["category"]}</span>', unsafe_allow_html=True)
                c2.markdown(f'<span style="font-size:12px;color:#6b7280">~{R(t["estimated_amount"])} · dia {t["due_day"]}</span>', unsafe_allow_html=True)
                if c3.button("✕",key=f"dtpl{t['id']}"): 
                    db.del_bill_template(t["id"]); LocalState.remove("bill_templates", t["id"])
            st.markdown('</div>', unsafe_allow_html=True)

def tab_planilha(month, d):
    inc   = d["income"];  fix=d["fixed"];  bills=d["bills"]
    cc_its= db.cc_items_from_data(d["cc_all"],month)
    subs  = [r for r in d["subs"] if r["active"]]
    ext   = d["extras"]; debts=d["debts"]
    pays=d["payments"]
    
    t_inc =sum(r["amount"] for r in inc)
    all_exp=[]
    for r in fix:    all_exp.append(("fixed",r["id"],r["label"],r["amount"],r["due_day"],"Gasto Fixo"))
    for r in bills:  all_exp.append(("bill",r["id"],r["label"],r["amount"],r["due_day"],"Conta"))
    for it in cc_its:all_exp.append(("cc",it["id"],f"{it['label']} ({it['installment']})",it["monthly"],30,"Cartão"))
    for r in subs:   all_exp.append(("sub",r["id"],r["label"],r["amount"],r["billing_day"],"Assinatura"))
    for r in ext:    all_exp.append(("ext",r["id"],r["label"],r["amount"],0,"Saída"))
    for debt in debts: all_exp.append(("debt",debt["id"],debt["label"],debt["monthly_payment"],debt.get("due_day",30),"Dívida"))
    
    all_exp.sort(key=lambda x:x[4])
    t_exp  = sum(x[3] for x in all_exp)
    t_paid = sum(p["amount"] for p in pays if p["paid"])
    t_pend = t_exp - t_paid

    st.markdown(f'<h2 style="font-size:20px;font-weight:700;color:#1a2332;margin:0 0 12px">Planilha de {ML(month)}</h2>', unsafe_allow_html=True)
    cols=st.columns(4,gap="small")
    with cols[0]: st.markdown(f'<div class="mc"><div class="mc-val" style="color:#16a34a">{R(t_inc)}</div><div class="mc-label">Entradas</div></div>', unsafe_allow_html=True)
    with cols[1]: st.markdown(f'<div class="mc"><div class="mc-val" style="color:#ef4444">{R(t_exp)}</div><div class="mc-label">Total saídas</div></div>', unsafe_allow_html=True)
    with cols[2]: st.markdown(f'<div class="mc"><div class="mc-val" style="color:#16a34a">{R(t_paid)}</div><div class="mc-label">✅ Já paguei</div></div>', unsafe_allow_html=True)
    with cols[3]: st.markdown(f'<div class="mc"><div class="mc-val" style="color:#ea580c">{R(t_pend)}</div><div class="mc-label">⏳ Falta pagar</div></div>', unsafe_allow_html=True)
    st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)

    left,right=st.columns([1.6,1],gap="medium")
    type_colors={"Gasto Fixo":"b-15","Conta":"b-red","Cartão":"b-amber","Assinatura":"b-blue","Saída":"b-gray","Dívida":"b-red"}
    with left:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="sec">Todas as saídas</div>', unsafe_allow_html=True)
        for (itype,iid,ilabel,iamt,iday,icat) in all_exp:
            paid=db.is_paid_fast(pays,month,itype,iid)
            c1,c2,c3,c4=st.columns([0.5,3.5,1.5,0.5])
            c1.markdown(f'<div style="padding-top:6px;font-size:16px">{"✅" if paid else "⬜"}</div>', unsafe_allow_html=True)
            c2.markdown(f'<div style="padding-top:4px;{"opacity:.35;" if paid else ""}"><span style="font-size:13px;font-weight:500">{ilabel}</span><br><span class="badge {type_colors.get(icat,"b-gray")}">{icat}</span>{f" · dia {iday}" if iday>0 else ""}</div>', unsafe_allow_html=True)
            c3.markdown(f'<div style="padding-top:6px;font-family:DM Mono,monospace;font-size:13px;color:{"#9ca3af" if paid else "#ef4444"}">{R(iamt)}</div>', unsafe_allow_html=True)
            if c4.button("✓" if not paid else "↩",key=f"pay_{itype}_{iid}"):
                LocalState.toggle_payment(month, itype, iid, iamt, not paid)
        st.markdown(f'<div style="display:flex;justify-content:space-between;padding:10px 0 0;border-top:2px solid var(--border);font-size:13px;font-weight:700"><span>Total</span><span style="font-family:DM Mono,monospace;color:#ef4444">{R(t_exp)}</span></div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    with right:
        st.markdown('<div class="card card-green">', unsafe_allow_html=True)
        st.markdown('<div class="sec">Entradas</div>', unsafe_allow_html=True)
        for r in inc:
            paid=db.is_paid_fast(pays,month,"income",r["id"])
            c1,c2,c3=st.columns([0.5,3,1])
            c1.markdown(f'<div style="padding-top:4px;font-size:14px">{"✅" if paid else "⬜"}</div>', unsafe_allow_html=True)
            c2.markdown(f'<div style="padding-top:2px"><span style="font-size:13px">{r["label"]}</span><br><span class="badge b-15">Dia {r["due_day"]}</span></div>', unsafe_allow_html=True)
            c3.markdown(f'<div style="padding-top:4px;font-family:DM Mono,monospace;font-size:13px;color:#16a34a">{R(r["amount"])}</div>', unsafe_allow_html=True)
            if st.button("✓" if not paid else "↩",key=f"pay_inc_{r['id']}"):
                LocalState.toggle_payment(month, "income", r["id"], r["amount"], not paid)
        st.markdown(f'<div style="display:flex;justify-content:space-between;padding:8px 0 0;border-top:1px solid var(--border);font-size:13px;font-weight:600"><span>Total</span><span style="font-family:DM Mono,monospace;color:#16a34a">{R(t_inc)}</span></div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        sobra=t_inc-t_exp
        st.markdown(f'<div class="card" style="text-align:center;border-top:3px solid {"#16a34a" if sobra>=0 else "#ef4444"}"><div style="font-size:10px;text-transform:uppercase;letter-spacing:1.5px;color:#6b7280;margin-bottom:5px">Resultado</div><div style="font-size:24px;font-weight:700;font-family:DM Mono,monospace;color:{"#16a34a" if sobra>=0 else "#ef4444"}">{R(sobra)}</div></div>', unsafe_allow_html=True)
        pct_pago=(t_paid/t_exp*100) if t_exp>0 else 0
        st.markdown(f'<div class="card"><div class="sec">Progresso</div><div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:4px"><span style="color:#16a34a">Pago: {R(t_paid)}</span><span style="color:#ea580c">Pendente: {R(t_pend)}</span></div>{prog_bar(pct_pago)}<div style="font-size:10px;color:#6b7280;margin-top:3px">{pct_pago:.0f}% pago</div></div>', unsafe_allow_html=True)

def tab_variavel(month, d):
    sub1,sub2,sub3,sub4=st.tabs(["💳 Cartão","🎬 Saídas","💸 Gastos Extras","📱 Assinaturas"])
    cc_all=d["cc_all"]; subs=d["subs"]; cfg=d["config"]
    items_m=db.cc_items_from_data(cc_all,month)
    total_m=db.cc_total_from_data(cc_all,month)
    extras=d["extras"]
    api_key=os.environ.get("GEMINI_API_KEY","") or cfg.get("api_key","")
    try: api_key=api_key or st.secrets.get("GEMINI_API_KEY","")
    except Exception: pass

    with sub1:
        st.markdown(f'<div style="display:flex;justify-content:space-between;align-items:center;padding:6px 0 14px"><div><h3 style="font-size:18px;font-weight:700;color:#1a2332;margin:0">Cartão de Crédito</h3><p style="color:#6b7280;font-size:12px;margin:2px 0 0">{len(items_m)} compra(s) em {ML(month)}</p></div><div style="font-size:20px;font-weight:700;color:#f59e0b;font-family:DM Mono,monospace">{R(total_m)}</div></div>', unsafe_allow_html=True)
        left,right=st.columns([1.2,1],gap="medium")
        with left:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown(f'<div class="sec">Cobranças de {ML(month)}</div>', unsafe_allow_html=True)
            if items_m:
                st.markdown('<table class="tbl"><thead><tr><th>Descrição</th><th>Cartão</th><th>Parcela</th><th>Valor</th></tr></thead><tbody>', unsafe_allow_html=True)
                for it in items_m:
                    st.markdown(f'<tr><td>{it["label"]}</td><td><span class="badge b-blue">{it["card"]}</span></td><td>{it["installment"]}</td><td style="font-family:DM Mono,monospace;color:#f59e0b">{R(it["monthly"])}</td></tr>', unsafe_allow_html=True)
                st.markdown(f'</tbody><tfoot><tr><td colspan="3"><b>Total</b></td><td style="font-family:DM Mono,monospace;color:#f59e0b"><b>{R(total_m)}</b></td></tr></tfoot></table>', unsafe_allow_html=True)
            else:
                st.markdown('<p style="color:#6b7280;font-size:13px">Nenhuma cobrança.</p>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown('<div class="sec">Todas as compras</div>', unsafe_allow_html=True)
            if cc_all:
                for it in cc_all:
                    c1,c2,c3=st.columns([3,2,1])
                    c1.markdown(f'<div style="font-size:12px;font-weight:500">{it["label"]}</div><div style="font-size:10px;color:#6b7280">{it["card_name"]} · {it["installments"]}x de {R(it["total_amount"]/it["installments"])} · {ML(it["start_month"])}</div>', unsafe_allow_html=True)
                    c2.markdown(f'<span style="font-family:DM Mono,monospace;font-size:12px;color:#6b7280">{R(it["total_amount"])}</span>', unsafe_allow_html=True)
                    if c3.button("✕",key=f"dcc{it['id']}"): 
                        db.del_cc(it["id"]); LocalState.remove("cc_all", it["id"])
            else:
                st.markdown('<p style="color:#6b7280;font-size:13px">Nenhuma compra.</p>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
        with right:
            st.markdown('<div class="card card-amber">', unsafe_allow_html=True)
            st.markdown('<div class="sec">Adicionar compra</div>', unsafe_allow_html=True)
            with st.form("add_cc"):
                l=st.text_input("Descrição","",placeholder="Ex: Notebook…"); a=st.number_input("Valor total (R$)",min_value=0.,step=10.,key="cc_valor")
                n=st.number_input("Parcelas",min_value=1,max_value=60,value=1,key="cc_parcelas")
                sm=st.text_input("Mês inicial",value=month); cn=st.text_input("Cartão","Cartão Principal")
                if st.form_submit_button("Adicionar", width="stretch"):
                    if l and a>0: 
                        rid = db.add_cc(l,a,int(n),sm,cn)
                        LocalState.add("cc_all", {"id":rid, "label":l, "total_amount":a, "installments":int(n), "start_month":sm, "card_name":cn})
            a_val=st.session_state.get("cc_valor",0.0); n_val=st.session_state.get("cc_parcelas",1)
            if n_val>1 and a_val>0:
                st.markdown(f'<div style="padding:8px 12px;background:#fffbeb;border-radius:8px;font-size:12px;color:#92400e;margin-top:4px">{int(n_val)}× de {R(a_val/n_val)}</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown('<div class="sec">Colar Fatura (IA)</div>', unsafe_allow_html=True)
            fatura=st.text_area("Texto da fatura","",height=100,placeholder="Cole aqui…",key="fatura_txt")
            card_n=st.text_input("Cartão","Cartão Principal",key="fatura_card")
            if st.button("Processar com IA",key="proc_f", width="stretch"):
                if api_key and fatura: _parse_fatura(api_key,fatura,month,card_n)
                elif not api_key: st.warning("Configure a chave API.")
                else: st.warning("Cole o texto.")
            st.markdown('</div>', unsafe_allow_html=True)

    with sub2:
        saidas=[r for r in extras if r.get("expense_type")=="saida"]
        t_saidas=sum(r["amount"] for r in saidas)
        st.markdown(f'<div style="display:flex;justify-content:space-between;align-items:center;padding:6px 0 10px"><h3 style="font-size:18px;font-weight:700;color:#1a2332;margin:0">Saídas — {ML(month)}</h3><div style="font-size:20px;font-weight:700;color:#6b7280;font-family:DM Mono,monospace">{R(t_saidas)}</div></div>', unsafe_allow_html=True)
        st.info("🎬 Saídas de lazer e consumo")
        left,right=st.columns([1.2,1],gap="medium")
        with left:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown('<div class="sec">Lançamentos</div>', unsafe_allow_html=True)
            if saidas:
                from collections import defaultdict
                grp=defaultdict(list)
                for r in saidas: grp[r["category"]].append(r)
                for cat,items in grp.items():
                    st.markdown(f'<div style="margin:6px 0 3px;display:flex;justify-content:space-between"><span class="badge b-gray">{cat}</span><span style="font-size:11px;color:#6b7280">{R(sum(i["amount"] for i in items))}</span></div>', unsafe_allow_html=True)
                    for r in items:
                        c1,c2,c3=st.columns([3,2,1])
                        c1.markdown(f'<span style="font-size:12px">{r["label"]}</span><br><span style="font-size:10px;color:#6b7280">{r["payment_method"]}</span>', unsafe_allow_html=True)
                        c2.markdown(f'<span style="font-family:DM Mono,monospace;font-size:12px">{R(r["amount"])}</span>', unsafe_allow_html=True)
                        if c3.button("✕",key=f"des{r['id']}"): 
                            db.del_extra(r["id"]); LocalState.remove("extras", r["id"])
            else:
                st.markdown('<p style="color:#6b7280;font-size:13px">Nenhuma saída.</p>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
        with right:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown('<div class="sec">Registrar saída</div>', unsafe_allow_html=True)
            with st.form("add_saida"):
                l=st.text_input("Descrição","",placeholder="Ex: Cinema, Restaurante…"); a=st.number_input("Valor (R$)",min_value=0.,step=5.)
                ca=st.selectbox("Categoria",CATS); pm=st.selectbox("Pagamento",PAY)
                fs=st.selectbox("Origem do Dinheiro", ["Salário do Mês", "Porquinho"])
                if st.form_submit_button("Registrar", width="stretch"):
                    if l and a>0: 
                        rid = db.add_extra(month,l,a,ca,pm,"saida",fs)
                        LocalState.add("extras", {"id":rid, "month":month, "label":l, "amount":a, "category":ca, "payment_method":pm, "expense_type":"saida", "fund_source": fs})
                    else: st.warning("Preencha os campos.")
            st.markdown('</div>', unsafe_allow_html=True)

    with sub3:
        exts=[r for r in extras if r.get("expense_type","extra")=="extra"]
        t_extras=sum(r["amount"] for r in exts)
        st.markdown(f'<div style="display:flex;justify-content:space-between;align-items:center;padding:6px 0 10px"><h3 style="font-size:18px;font-weight:700;color:#1a2332;margin:0">Gastos Extras</h3><div style="font-size:20px;font-weight:700;color:#6b7280;font-family:DM Mono,monospace">{R(t_extras)}</div></div>', unsafe_allow_html=True)
        st.info("💸 PIX, dinheiro e transferências")
        left,right=st.columns([1.2,1],gap="medium")
        with left:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown('<div class="sec">Gastos</div>', unsafe_allow_html=True)
            if exts:
                st.markdown('<table class="tbl"><thead><tr><th>Descrição</th><th>Categoria</th><th>Método</th><th>Valor</th></tr></thead><tbody>', unsafe_allow_html=True)
                for r in exts:
                    st.markdown(f'<tr><td>{r["label"]}</td><td><span class="badge b-gray">{r["category"]}</span></td><td>{r["payment_method"]}</td><td style="font-family:DM Mono,monospace">{R(r["amount"])}</td></tr>', unsafe_allow_html=True)
                st.markdown(f'</tbody><tfoot><tr><td colspan="3"><b>Total</b></td><td style="font-family:DM Mono,monospace"><b>{R(t_extras)}</b></td></tr></tfoot></table>', unsafe_allow_html=True)
                for r in exts:
                    if st.button("✕",key=f"dex{r['id']}"): 
                        db.del_extra(r["id"]); LocalState.remove("extras", r["id"])
            else:
                st.markdown('<p style="color:#6b7280;font-size:13px">Nenhum gasto.</p>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
        with right:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown('<div class="sec">Registrar</div>', unsafe_allow_html=True)
            with st.form("add_extra"):
                l=st.text_input("Descrição","",placeholder="Ex: Padaria, Farmácia…"); a=st.number_input("Valor (R$)",min_value=0.,step=5.)
                ca=st.selectbox("Categoria",CATS); pm=st.selectbox("Método",["PIX","Dinheiro","Transferência","Débito","Outro"])
                fs=st.selectbox("Origem do Dinheiro", ["Salário do Mês", "Porquinho"])
                if st.form_submit_button("Registrar", width="stretch"):
                    if l and a>0: 
                        rid = db.add_extra(month,l,a,ca,pm,"extra",fs)
                        LocalState.add("extras", {"id":rid, "month":month, "label":l, "amount":a, "category":ca, "payment_method":pm, "expense_type":"extra", "fund_source": fs})
                    else: st.warning("Preencha os campos.")
            st.markdown('</div>', unsafe_allow_html=True)

    with sub4:
        t_subs=sum(r["amount"] for r in subs if r["active"])
        st.markdown(f'<div style="display:flex;justify-content:space-between;align-items:center;padding:6px 0 14px"><h3 style="font-size:18px;font-weight:700;color:#1a2332;margin:0">Assinaturas</h3><div style="font-size:20px;font-weight:700;color:#8b5cf6;font-family:DM Mono,monospace">{R(t_subs)}/mês · {R(t_subs*12)}/ano</div></div>', unsafe_allow_html=True)
        left,right=st.columns([1.3,1],gap="medium")
        with left:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown('<div class="sec">Suas assinaturas</div>', unsafe_allow_html=True)
            if subs:
                st.markdown('<table class="tbl"><thead><tr><th>Serviço</th><th>Categoria</th><th>Dia</th><th>Valor</th><th>Status</th></tr></thead><tbody>', unsafe_allow_html=True)
                for r in subs:
                    badge='<span class="badge b-green">Ativa</span>' if r["active"] else '<span class="badge b-gray">Pausada</span>'
                    st.markdown(f'<tr><td style="font-weight:500">{r["label"]}</td><td><span class="badge b-gray">{r["category"]}</span></td><td>{r["billing_day"]}</td><td style="font-family:DM Mono,monospace;color:#8b5cf6">{R(r["amount"])}</td><td>{badge}</td></tr>', unsafe_allow_html=True)
                st.markdown(f'</tbody><tfoot><tr><td colspan="3"><b>Total</b></td><td style="font-family:DM Mono,monospace;color:#8b5cf6"><b>{R(t_subs)}</b></td><td></td></tr></tfoot></table>', unsafe_allow_html=True)
                for r in subs:
                    c1,c2,c3=st.columns([4,1,1])
                    c1.write(r["label"])
                    if c2.button("⏸" if r["active"] else "▶",key=f"ts{r['id']}"): 
                        db.toggle_sub(r["id"]); LocalState.update("subs", r["id"], active=0 if r["active"] else 1)
                    if c3.button("✕",key=f"ds{r['id']}"): 
                        db.del_sub(r["id"]); LocalState.remove("subs", r["id"])
            else:
                st.markdown('<p style="color:#6b7280;font-size:13px">Nenhuma assinatura.</p>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
        with right:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown('<div class="sec">Adicionar</div>', unsafe_allow_html=True)
            with st.form("add_sub"):
                l=st.text_input("Serviço","",placeholder="Ex: Netflix…"); a=st.number_input("Valor/mês",min_value=0.,step=1.)
                ca=st.selectbox("Categoria",["Entretenimento","Educação","Software","Saúde","Outros"])
                bd=st.number_input("Dia débito",min_value=1,max_value=31,value=1)
                if st.form_submit_button("Adicionar", width="stretch"):
                    if l and a>0: 
                        rid = db.add_sub(l,a,ca,int(bd))
                        LocalState.add("subs", {"id":rid, "label":l, "amount":a, "category":ca, "billing_day":int(bd), "active":1})
            st.markdown('</div>', unsafe_allow_html=True)

def _parse_fatura(api_key, text, month, card_name):
    import google.generativeai as genai
    genai.configure(api_key=api_key)
    system='Analise a fatura e retorne APENAS um JSON array válido neste formato exato: [{"label":"NOME","total_amount":VALOR,"installments":1,"start_month":"AAAA-MM"}]. Para compras parceladas, total_amount é o valor total da compra. Sem explicações ou markdown em volta.'
    
    try:
        model = genai.GenerativeModel('gemini-2.5-flash', system_instruction=system)
        r = model.generate_content(f"Fatura {month}:\n{text}")
        raw = r.text.strip().replace("```json","").replace("```","").strip()
        items = json.loads(raw)
        count = 0
        for it in items:
            if "label" in it and "total_amount" in it:
                db.add_cc(it["label"],float(it["total_amount"]),int(it.get("installments",1)),it.get("start_month",month),card_name); count+=1
        st.success(f"✅ {count} item(s) importado(s)!"); LocalState.reload()
    except Exception as e: st.error(f"Erro ao processar fatura: {e}")

def tab_guardado(month, d):
    prev_month = prev_m(month)
    prev_leftover = LocalState.get_leftover(prev_month)
    
    invs = [r for r in d["investments"] if r["month"] == month]
    man_saved = sum(float(r["amount_added"]) for r in invs)
    
    total_mes = man_saved + (prev_leftover if prev_leftover > 0 else 0)

    st.markdown(f'<div style="display:flex;justify-content:space-between;align-items:center;padding:6px 0 14px"><div><h2 style="font-size:20px;font-weight:700;color:#1a2332;margin:0">O Porquinho 🐷</h2><p style="color:#6b7280;font-size:12px;margin:3px 0 0">Sobra do mês passado + Guardado carimbado</p></div><div style="font-size:20px;font-weight:700;color:#3b82f6;font-family:DM Mono,monospace">{R(total_mes)}</div></div>', unsafe_allow_html=True)
    
    left,right=st.columns([1.2,1],gap="medium")
    with left:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown(f'<div class="sec">Sobra Automática ({ML(prev_month)})</div>', unsafe_allow_html=True)
        if prev_leftover > 0:
            st.markdown(f'<div style="padding:10px 0;display:flex;justify-content:space-between;align-items:center"><span style="font-size:14px;color:#374151">Saldo que não foi gasto no mês passado</span><span style="font-family:DM Mono,monospace;font-size:18px;color:#16a34a;font-weight:600">+{R(prev_leftover)}</span></div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div style="padding:10px 0;display:flex;justify-content:space-between;align-items:center"><span style="font-size:14px;color:#9ca3af">Não houve sobra no mês passado.</span><span style="font-family:DM Mono,monospace;font-size:18px;color:#9ca3af;font-weight:600">{R(0)}</span></div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="card card-blue">', unsafe_allow_html=True)
        st.markdown('<div class="sec">Guardado com Destino Carimbado</div>', unsafe_allow_html=True)
        if invs:
            st.markdown('<table class="tbl"><thead><tr><th>Destino/Motivo</th><th>Valor</th></tr></thead><tbody>', unsafe_allow_html=True)
            for r in invs:
                st.markdown(f'<tr><td>{r["notes"]}</td><td style="font-family:DM Mono,monospace;color:#3b82f6">{R(r["amount_added"])}</td></tr>', unsafe_allow_html=True)
            st.markdown('</tbody></table>', unsafe_allow_html=True)
            for r in invs:
                if st.button(f"✕ {r['notes']}",key=f"del_inv_{r['id']}"): 
                    db.del_guardado(r["id"]); LocalState.remove("investments", r["id"])
        else:
            st.markdown('<p style="color:#6b7280;font-size:13px">Nenhum valor carimbado este mês.</p>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with right:
        st.markdown('<div class="card card-blue">', unsafe_allow_html=True)
        st.markdown('<div class="sec">+ Separar Dinheiro</div>', unsafe_allow_html=True)
        with st.form("add_inv"):
            nt_=st.text_input("Destino", placeholder="Ex: 300 para Isa, 100 mercado...")
            aad=st.number_input("Valor (R$)",min_value=0.,step=100.)
            if st.form_submit_button("Guardar", width="stretch"):
                if aad>0 and nt_: 
                    rid = db.add_guardado(month, aad, nt_)
                    LocalState.add("investments", {"id":rid, "month":month, "amount_added":aad, "notes":nt_})
                else: st.warning("Informe o destino e o valor.")
        st.markdown('</div>', unsafe_allow_html=True)

def tab_dividas(d):
    debts=d["debts"]
    t_rem=sum(r["remaining_amount"] for r in debts); t_mp=sum(r["monthly_payment"] for r in debts)
    st.markdown(f'<div style="display:flex;justify-content:space-between;align-items:center;padding:6px 0 14px"><div><h2 style="font-size:20px;font-weight:700;color:#1a2332;margin:0">Dívidas</h2></div><div style="font-size:20px;font-weight:700;color:#ef4444;font-family:DM Mono,monospace">{R(t_rem)}</div></div>', unsafe_allow_html=True)
    cols=st.columns(3,gap="small")
    with cols[0]: st.markdown(f'<div class="mc"><div class="mc-val" style="color:#ef4444">{R(t_rem)}</div><div class="mc-label">Saldo devedor</div></div>', unsafe_allow_html=True)
    with cols[1]: st.markdown(f'<div class="mc"><div class="mc-val" style="color:#f59e0b">{R(t_mp)}</div><div class="mc-label">Parcelas/mês</div></div>', unsafe_allow_html=True)
    with cols[2]:
        if debts:
            worst=max(debts,key=lambda x:x["interest_rate"])
            st.markdown(f'<div class="mc"><div class="mc-val" style="color:#ef4444">{worst["interest_rate"]:.1f}%a.m.</div><div class="mc-label">Maior juros</div></div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="mc"><div class="mc-val" style="color:#16a34a">0%</div><div class="mc-label">Sem juros</div></div>', unsafe_allow_html=True)
    st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)
    left,right=st.columns([1.3,1],gap="medium")
    with left:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="sec">Suas Dívidas</div>', unsafe_allow_html=True)
        if debts:
            for r in debts:
                mz=db.months_to_zero(r["remaining_amount"],r["monthly_payment"],r["interest_rate"])
                if mz<=12:   alert=f'<span class="badge b-green">Zera em {mz} meses</span>'
                elif mz<=24: alert=f'<span class="badge b-amber">Zera em {mz} meses</span>'
                else:        alert=f'<span class="badge b-red">⚠️ {mz} meses</span>'
                pct=max(0,min(100,(1-r["remaining_amount"]/r["total_amount"])*100)) if r["total_amount"]>0 else 0
                ciclo_badge=f'<span class="badge b-{"15" if r.get("due_day",30)<=15 else "30"}" style="font-size:9px">Dia {r.get("due_day",30)}</span>'
                st.markdown(f'<div style="padding:10px 0;border-bottom:1px solid var(--border)"><div style="display:flex;justify-content:space-between;align-items:flex-start"><div><div style="font-weight:600;font-size:13px">{r["label"]} {ciclo_badge}</div><div style="font-size:11px;color:#6b7280">Restante: <b style="color:#ef4444">{R(r["remaining_amount"])}</b> · Parcela: {R(r["monthly_payment"])} · Juros: {r["interest_rate"]:.1f}%a.m.</div></div>{alert}</div>{prog_bar(pct)}</div>', unsafe_allow_html=True)
                ca,cb,cc_col=st.columns([1.5,0.7,0.7])
                nv=ca.number_input("Saldo",value=float(r["remaining_amount"]),step=100.,key=f"dr{r['id']}")
                if ca.button("Salvar",key=f"dsr{r['id']}"): 
                    db.update_debt_remaining(r["id"],nv); LocalState.update("debts", r["id"], remaining_amount=nv)
                other_d=15 if r.get("due_day",30)==30 else 30
                if cb.button(f"→{other_d}",key=f"mvd{r['id']}"): 
                    db.update_debt_due_day(r["id"],other_d); LocalState.update("debts", r["id"], due_day=other_d)
                if cc_col.button("✕",key=f"dd{r['id']}"): 
                    db.del_debt(r["id"]); LocalState.remove("debts", r["id"])
        else:
            st.markdown('<div class="diag-ok">🎉 Sem dívidas! Excelente!</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    with right:
        st.markdown('<div class="card card-red">', unsafe_allow_html=True)
        st.markdown('<div class="sec">Cadastrar Dívida</div>', unsafe_allow_html=True)
        with st.form("add_debt"):
            l=st.text_input("Descrição","",placeholder="Ex: Empréstimo…"); total=st.number_input("Valor original (R$)",min_value=0.,step=100.)
            rem=st.number_input("Saldo devedor (R$)",min_value=0.,step=100.); mp=st.number_input("Parcela mensal (R$)",min_value=0.,step=50.)
            ir=st.number_input("Juros mensais (%)",min_value=0.,step=0.1); ciclo_d=st.selectbox("Ciclo",[30,15]); nt_=st.text_input("Obs.","")
            if st.form_submit_button("Cadastrar", width="stretch"):
                if l and total>0 and mp>0: 
                    rid = db.add_debt(l,total,rem or total,mp,ir,int(ciclo_d),nt_)
                    LocalState.add("debts", {"id":rid, "label":l, "total_amount":total, "remaining_amount":rem or total, "monthly_payment":mp, "interest_rate":ir, "due_day":int(ciclo_d)})
                else: st.warning("Preencha os campos.")
        st.markdown('</div>', unsafe_allow_html=True)

def tab_metas(d):
    goals=d["goals"]
    t_tg=sum(g["target_amount"] for g in goals); t_cur=sum(g["current_amount"] for g in goals)
    st.markdown(f'<div style="display:flex;justify-content:space-between;align-items:center;padding:6px 0 14px"><div><h2 style="font-size:20px;font-weight:700;color:#1a2332;margin:0">Metas Financeiras</h2></div><div style="font-size:14px;font-weight:600;color:#16a34a;font-family:DM Mono,monospace">{R(t_cur)} / {R(t_tg)}</div></div>', unsafe_allow_html=True)
    left,right=st.columns([1.3,1],gap="medium")
    with left:
        st.markdown('<div class="card card-green">', unsafe_allow_html=True)
        st.markdown('<div class="sec">Suas Metas</div>', unsafe_allow_html=True)
        if goals:
            for g in goals:
                pct=min(100,(g["current_amount"]/g["target_amount"]*100)) if g["target_amount"]>0 else 0
                color="#16a34a" if pct>=100 else "#3b82f6"
                falta=max(0,g["target_amount"]-g["current_amount"])
                st.markdown(f'<div style="padding:12px 0;border-bottom:1px solid var(--border)"><div style="display:flex;justify-content:space-between;margin-bottom:4px"><span style="font-weight:600;font-size:13px">{g["label"]}</span>{"<span class=badge b-green>✅ Concluída</span>" if pct>=100 else ""}</div><div style="display:flex;justify-content:space-between;font-size:12px;color:#6b7280;margin-bottom:4px"><span>Acumulado: <b style="color:#16a34a">{R(g["current_amount"])}</b></span><span>Meta: <b>{R(g["target_amount"])}</b></span></div>{prog_bar(pct,color)}<div style="display:flex;justify-content:space-between;font-size:10px;color:#6b7280;margin-top:2px"><span>{pct:.0f}% · Falta {R(falta)}</span><span>{g["deadline"]}</span></div></div>', unsafe_allow_html=True)
                ca,cb,cc_g=st.columns([2,1,1])
                nv=ca.number_input("Valor atual",value=float(g["current_amount"]),step=100.,key=f"gu{g['id']}")
                if cb.button("Salvar",key=f"gs{g['id']}"): 
                    db.update_goal(g["id"],nv); LocalState.update("goals", g["id"], current_amount=nv)
                if cc_g.button("✕",key=f"gd{g['id']}"): 
                    db.del_goal(g["id"]); LocalState.remove("goals", g["id"])
        else:
            st.markdown('<p style="color:#6b7280;font-size:13px">Nenhuma meta.</p>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    with right:
        st.markdown('<div class="card card-green">', unsafe_allow_html=True)
        st.markdown('<div class="sec">Cadastrar Meta</div>', unsafe_allow_html=True)
        with st.form("add_goal"):
            l=st.text_input("Meta","",placeholder="Ex: Viagem Europa…"); tg=st.number_input("Valor alvo (R$)",min_value=0.,step=500.)
            cur_g=st.number_input("Já tenho (R$)",min_value=0.,step=100.); dl=st.text_input("Prazo",""); nt_=st.text_input("Obs.","")
            if st.form_submit_button("Cadastrar", width="stretch"):
                if l and tg>0: 
                    rid = db.add_goal(l,tg,cur_g,dl,nt_)
                    LocalState.add("goals", {"id":rid, "label":l, "target_amount":tg, "current_amount":cur_g, "deadline":dl})
                else: st.warning("Preencha os campos.")
        st.markdown('</div>', unsafe_allow_html=True)

def tab_visualizacao_anual(month):
    st.markdown(f'<h2 style="font-size:22px;font-weight:700;color:#1a2332;margin-bottom:4px">Projeção de 24 Meses</h2>', unsafe_allow_html=True)
    st.markdown(f'<p style="color:#6b7280;font-size:13px;margin-bottom:20px">Iniciando em {ML(month)} (Baseado em Rendas, Fixos e Parcelamentos atuais)</p>', unsafe_allow_html=True)

    data = db.get_projection_data(month, 24)

    html = """<div style="overflow-x:auto"><table class="tbl">
    <thead>
        <tr>
            <th>Mês</th>
            <th style="background:#dbeafe;color:#1e40af">Renda 15</th>
            <th style="background:#fee2e2;color:#991b1b">Contas 15</th>
            <th style="border-right:2px solid #e5e7eb;font-weight:800">Sobra 15</th>
            <th style="background:#ede9fe;color:#5b21b6">Renda 30</th>
            <th style="background:#fef3c7;color:#92400e">Contas 30</th>
            <th style="border-right:2px solid #e5e7eb;font-weight:800">Sobra 30</th>
            <th style="background:var(--green);color:white;font-weight:800">Sobra Geral</th>
        </tr>
    </thead>
    <tbody>"""

    for r in data:
        c15 = "#16a34a" if r['sobra_15'] >= 0 else "#ef4444"
        c30 = "#16a34a" if r['sobra_30'] >= 0 else "#ef4444"
        cg  = "#16a34a" if r['sobra_geral'] >= 0 else "#ef4444"
        
        html += f"""
        <tr>
            <td style="font-weight:600">{ML(r['mes'])}</td>
            <td style="color:#1e40af">{R(r['inc_15'])}</td>
            <td style="color:#991b1b">{R(r['gas_15'])}</td>
            <td style="font-family:DM Mono; font-weight:700; color:{c15}; border-right:2px solid #e5e7eb">{R(r['sobra_15'])}</td>
            <td style="color:#5b21b6">{R(r['inc_30'])}</td>
            <td style="color:#92400e">{R(r['gas_30'])}</td>
            <td style="font-family:DM Mono; font-weight:700; color:{c30}; border-right:2px solid #e5e7eb">{R(r['sobra_30'])}</td>
            <td style="font-family:DM Mono; font-weight:800; color:{cg}; background:#f0fdf4">{R(r['sobra_geral'])}</td>
        </tr>
        """
    
    html += "</tbody></table></div>"
    st.markdown(html, unsafe_allow_html=True)

def tab_assistente(month, d):
    st.markdown('<div style="text-align:center;padding:10px 0 20px"><h2 style="font-size:22px;font-weight:700;color:#1a2332;margin:0">Gestor Financeiro IA</h2><p style="color:#6b7280;font-size:13px;margin-top:5px">Conselheiro e organizador prático da família</p></div>', unsafe_allow_html=True)
    cfg=d["config"]; inc=d["income"]; fix=d["fixed"]; ext=d["extras"]; subs=d["subs"]
    debts=d["debts"]; invs=d["investments"]; goals=d["goals"]
    
    api_key=os.environ.get("GEMINI_API_KEY","") or cfg.get("api_key","")
    try: api_key=api_key or st.secrets.get("GEMINI_API_KEY","")
    except Exception: pass
    
    if not api_key: st.warning("Configure a chave API do Google Gemini em ⚙️ Configurações."); return
    
    cc=db.cc_total_from_data(d["cc_all"],month)
    t_inc=sum(r["amount"] for r in inc); t_fix=sum(r["amount"] for r in fix)
    t_ext=sum(r["amount"] for r in ext); t_subs=sum(r["amount"] for r in subs if r["active"])
    t_debt_m=sum(r["monthly_payment"] for r in debts); t_debt_t=sum(r["remaining_amount"] for r in debts)
    t_inv=sum(float(r["amount_added"]) for r in invs if r["month"]==month)
    
    _,c,_=st.columns([1,2,1])
    with c:
        if st.button("🤝 Pedir Conselho sobre este mês", width="stretch"):
            _run_ai_full(api_key,month,t_inc,t_fix,t_ext,t_subs,cc,t_debt_m,t_debt_t,t_inv,0,goals,debts,subs,fix,inc)
    
    key=f"ai_{month}"
    if key in st.session_state:
        st.markdown(f'<div style="background:#f8fafc;border:1px solid #e5e7eb;border-left:4px solid #00c896;border-radius:12px;padding:22px 26px;margin-top:18px;font-size:14px;line-height:1.8;color:#374151;max-width:780px;margin-inline:auto">{st.session_state[key].replace(chr(10),"<br>")}</div>', unsafe_allow_html=True)
        qs=["Como acelerar o pagamento das dívidas este mês?","Qual é o nosso principal ralo de dinheiro?","Dê uma dica para a gente economizar sem perder a qualidade de vida."]
        qc=st.columns(3)
        for i,q in enumerate(qs):
            if qc[i%3].button(q,key=f"q{i}"):
                _run_ai_q(api_key,q,month,t_inc,t_fix+cc+t_subs+t_ext,t_debt_t,t_inv,0)
    
    if f"ai_q_{month}" in st.session_state:
        st.markdown(f'<div style="background:white;border:1px solid #e5e7eb;border-radius:10px;padding:14px 18px;margin-top:10px;font-size:13px;line-height:1.7;max-width:780px;margin-inline:auto">{st.session_state[f"ai_q_{month}"].replace(chr(10),"<br>")}</div>', unsafe_allow_html=True)

def _run_ai_full(api_key,month,t_inc,t_fix,t_ext,t_subs,cc,t_debt_m,t_debt_t,t_inv,ef,goals,debts,subs,fix,inc):
    import google.generativeai as genai
    genai.configure(api_key=api_key)
    
    g_txt="\n".join([f"  · {g['label']}: {R(g['current_amount'])}/{R(g['target_amount'])} ({g['deadline']})" for g in goals]) or "  Nenhuma"
    d_txt="\n".join([f"  · {d['label']}: R${d['remaining_amount']:.0f} rest, {R(d['monthly_payment'])}/mês, {d['interest_rate']:.1f}%a.m." for d in debts]) or "  Nenhuma"
    s_txt="\n".join([f"  · {s['label']}: {R(s['amount'])}/mês" for s in subs if s["active"]]) or "  Nenhuma"
    
    prompt=f"""DADOS — {ML(month)}: Renda: R${t_inc:.0f} | Gastos: R${t_fix+cc+t_subs+t_ext:.0f} ({((t_fix+cc+t_subs+t_ext)/t_inc*100 if t_inc>0 else 0):.0f}%) | Sobra: R${t_inc-t_fix-cc-t_subs-t_ext-t_debt_m:.0f}
Dívidas/mês: R${t_debt_m:.0f} | Total dívidas: R${t_debt_t:.0f} | Porquinho: R${t_inv:.0f}
Assinaturas: {s_txt} | Dívidas: {d_txt} | Metas: {g_txt}"""

    system="Você é o consultor financeiro pessoal, cordial e acolhedor da família (Priscila, Thiago e a pequena Isa). Sem palavrões, sempre respeitoso e prático. Dê conselhos como um amigo especialista. Se gastaram muito (ex: mercado, extras), puxe a orelha com carinho. Se sobrou, elogie, sugira pegar uns 100 reais para um hambúrguer pro casal e destinar o resto pras dívidas ou pro Porquinho. Seu objetivo é encorajá-los de que, com disciplina, as dívidas vão sumir. Estrutura: 1. Diagnóstico do Mês 2. Ponto de Atenção 3. Conselho Prático. Máx 300 palavras."
    
    with st.spinner("Analisando a situação de vocês..."):
        try:
            model = genai.GenerativeModel('gemini-2.5-flash', system_instruction=system)
            r = model.generate_content(prompt)
            st.session_state[f"ai_{month}"]=r.text; st.rerun()
        except Exception as e: st.error(f"Erro ao consultar Gemini: {e}")

def _run_ai_q(api_key,question,month,t_inc,t_gasto,t_debt,t_inv,ef):
    import google.generativeai as genai
    genai.configure(api_key=api_key)
    
    ctx=f"Renda do casal Priscila e Thiago: R${t_inc:.0f} · Gastos: R${t_gasto:.0f} · Dívidas: R${t_debt:.0f} · Porquinho: R${t_inv:.0f}"
    
    with st.spinner("..."):
        try:
            model = genai.GenerativeModel(
                'gemini-2.5-flash', 
                system_instruction="Você é o consultor financeiro amigo e empático de Priscila e Thiago (que têm uma filha de 6 anos, Isa). Dê respostas curtas, práticas, sem palavrões e sempre encorajadoras. Max 200 palavras."
            )
            r = model.generate_content(f"Contexto financeiro: {ctx}\n\nPergunta da Priscila: {question}")
            st.session_state[f"ai_q_{month}"]=r.text; st.rerun()
        except Exception as e: st.error(f"Erro ao consultar Gemini: {e}")

def tab_config(d):
    cfg=d["config"]
    st.markdown('<h2 style="font-size:20px;font-weight:700;color:#1a2332;margin:0 0 18px">Configurações</h2>', unsafe_allow_html=True)
    c1,c2=st.columns(2,gap="medium")
    with c1:
        st.markdown('<div class="card card-green">', unsafe_allow_html=True)
        st.markdown('<div class="sec">Alterar Senha</div>', unsafe_allow_html=True)
        with st.form("pwd"):
            cur_=st.text_input("Senha atual",type="password"); n1=st.text_input("Nova senha",type="password"); n2=st.text_input("Confirmar",type="password")
            if st.form_submit_button("Alterar", width="stretch"):
                if not db.check_pwd(cur_): st.error("Senha incorreta.")
                elif n1!=n2: st.error("Senhas não coincidem.")
                elif len(n1)<4: st.error("Mínimo 4 caracteres.")
                else: db.change_pwd(n1); st.success("✅ Senha alterada.")
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="sec">Desfazer</div>', unsafe_allow_html=True)
        if st.button("↩ Desfazer última ação", width="stretch"):
            ok,msg=db.undo_last(); (st.success if ok else st.warning)(msg); LocalState.reload()
        st.markdown('</div>', unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="card card-green">', unsafe_allow_html=True)
        st.markdown('<div class="sec">Chave API Gemini (Google)</div>', unsafe_allow_html=True)
        cur_k=cfg.get("api_key",""); masked=f"AIzaSy…{cur_k[-6:]}" if cur_k else "não configurada"
        st.markdown(f'<p style="font-size:12px;color:#6b7280;margin-bottom:8px">Atual: <code>{masked}</code></p>', unsafe_allow_html=True)
        with st.form("api"):
            k=st.text_input("Nova chave","",placeholder="AIzaSy...")
            if st.form_submit_button("Salvar", width="stretch"):
                if k.startswith("AIzaSy"): db.set_api_key(k); st.success("✅ Salva."); LocalState.reload()
                else: st.warning("A chave do Gemini deve começar com 'AIzaSy'")
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="sec">Banco de dados</div>', unsafe_allow_html=True)
        st.markdown('<div class="diag-ok">🟢 Supabase + Optimistic UI + Gemini AI</div>', unsafe_allow_html=True)
        st.markdown(f'<div style="font-size:12px;color:#6b7280;line-height:2;margin-top:8px">Pool · <span style="color:#374151">2–10 conexões (ThreadedConnectionPool)</span><br>Cache · <span style="color:#374151">LocalState Engine RAM-First</span><br>Versão · <span style="color:#00c896;font-weight:600">12.1 — Family Edition</span></div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        if st.button("🔄 Forçar recarga do banco", width="stretch"):
            LocalState.reload()

def main():
    st.markdown(CSS, unsafe_allow_html=True)

    if "_pool" not in st.session_state:
        with st.spinner("Conectando ao banco…"):
            ok, err = db.init_db()
        if not ok:
            st.error(f"**Erro de conexão:** {err}")
            st.markdown("""
            **Como corrigir:**
            Verifique se suas variáveis estão configuradas corretamente nos **Secrets do Streamlit Cloud**.
            """)
            if st.button("🔄 Tentar reconectar", width="stretch"):
                st.rerun()
            return

    if "auth" not in st.session_state:
        st.session_state.auth = False
    if not st.session_state.auth:
        try:
            t = st.query_params.get("t","")
            if t and _check_token(t): st.session_state.auth = True
        except Exception: pass
    if not st.session_state.auth:
        login_page(); return

    if "month" not in st.session_state:
        st.session_state.month = datetime.now().strftime("%Y-%m")
    month = sidebar(st.session_state.month)

    d = LocalState.get(month)

    tabs = st.tabs(["📊 Painel", "💰 Renda", "🏠 Contas Fixas", "📋 Planilha", "💳 Variável", "🐷 Guardado", "⚠️ Dívidas", "🎯 Metas", "📅 24 Meses", "🤖 Gestor IA", "⚙️ Config"])
    t1,t2,t3,t4,t5,t6,t7,t8,t9,t10,t11 = tabs
    
    with t1: tab_painel(month, d)
    with t2: tab_renda(month, d)
    with t3: tab_contas(month, d)
    with t4: tab_planilha(month, d)
    with t5: tab_variavel(month, d)
    with t6: tab_guardado(month, d)
    with t7: tab_dividas(d)
    with t8: tab_metas(d)
    with t9: tab_visualizacao_anual(month)
    with t10: tab_assistente(month, d)
    with t11: tab_config(d)

if __name__ == "__main__":
    main()
