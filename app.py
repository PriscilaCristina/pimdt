"""
app.py — minhasFinanças · Família Peixoto
Performance: @st.cache_resource no pool + @st.cache_data(ttl=8) por mês.
Uma única chamada batch por página; cache limpo somente após mutações.
"""

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
CATS = ["Moradia","Transporte","Saúde","Educação","Alimentação","Lazer",
        "Streaming","Serviços","Vestuário","Outros"]
PAY  = ["PIX","Dinheiro","Débito","Transferência","Outro"]

# ── Helpers de formatação ─────────────────────────────────────────────────────
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

# ── Invalida cache após qualquer mutação ──────────────────────────────────────
def _mutated():
    st.cache_data.clear()
    st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# CACHE DE DADOS — chamado UMA vez por mês, resultado mantido 8 segundos
# ══════════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=8, show_spinner=False)
def _load(month: str) -> dict:
    return db.get_month_data(month)

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
.stTabs [data-baseweb="tab-list"]{gap:0;border-bottom:2px solid var(--border);background:transparent;padding:0}
.stTabs [data-baseweb="tab"]{background:transparent!important;color:var(--muted)!important;font-family:'Inter',sans-serif!important;font-size:13px!important;font-weight:500!important;padding:10px 16px!important;border-radius:0!important;border-bottom:2px solid transparent!important;margin-bottom:-2px}
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
.diag-ok{background:#f0fdf4;border:1px solid #bbf7d0;border-radius:10px;padding:10px 14px;color:#166534;font-size:13px;margin-bottom:6px}
.diag-warn{background:#fffbeb;border:1px solid #fde68a;border-radius:10px;padding:10px 14px;color:#92400e;font-size:13px;margin-bottom:6px}
.diag-crit{background:#fef2f2;border:1px solid #fecaca;border-radius:10px;padding:10px 14px;color:#991b1b;font-size:13px;margin-bottom:6px}
</style>"""


# ══════════════════════════════════════════════════════════════════════════════
# AUTH
# ══════════════════════════════════════════════════════════════════════════════
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
        if st.button("Entrar →", use_container_width=True):
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
                st.error("Senha incorreta. Padrão: 1234")
        st.markdown('<p style="text-align:center;color:#d1d5db;font-size:11px;margin-top:14px">🟢 Supabase · Dados seguros</p>',
                    unsafe_allow_html=True)


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
            st.markdown(f'<div style="text-align:center;padding:6px 0;font-size:14px;font-weight:600;color:#1a2332">{ML(month)}</div>',
                        unsafe_allow_html=True)
        with c3:
            if st.button("▶", key="n"):
                st.session_state.month = next_m(month); st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
        st.divider()
        if st.button("↩ Desfazer última ação", use_container_width=True):
            ok, msg = db.undo_last()
            (st.success if ok else st.warning)(msg)
            _mutated()
        st.markdown('<div style="height:4px"></div>', unsafe_allow_html=True)
        if st.button("⊕ Copiar mês anterior", use_container_width=True):
            n = db.copy_fixed_prev(month)
            st.success(f"{n} itens copiados") if n > 0 else st.info("Já existem ou nenhum.")
            _mutated()
        st.divider()
        st.markdown('<div style="font-size:10px;color:#16a34a;text-align:center;padding:2px 0">🟢 Supabase conectado</div>',
                    unsafe_allow_html=True)
        st.divider()
        if st.button("↪ Sair", use_container_width=True):
            st.session_state.auth = False
            try: st.query_params.clear()
            except Exception: pass
            st.rerun()
    return st.session_state.month


# ══════════════════════════════════════════════════════════════════════════════
# PAINEL
# ══════════════════════════════════════════════════════════════════════════════
def tab_painel(month, d):
    inc   = d["income"]
    fix   = d["fixed"]
    ext   = d["extras"]
    subs  = d["subs"]
    debts = d["debts"]
    bills = d["bills"]
    invs  = d["investments"]
    goals = d["goals"]
    ins   = d["insurance"]
    pays  = d["payments"]
    cfg   = d["config"]
    ef    = d["ef"]
    cc_all= d["cc_all"]

    cc       = db.cc_total_from_data(cc_all, month)
    inv_this = next((float(r["amount_added"]) for r in invs if r["month"]==month), 0.0)
    t_inv    = db.investment_last_total(invs)
    t_ins    = db.insurance_total_from_data(ins)
    ef_target= float(cfg.get("ef_target","0") or 0)

    t_inc  = sum(r["amount"] for r in inc)
    t_fix  = sum(r["amount"] for r in fix)
    t_ext  = sum(r["amount"] for r in ext)
    t_subs = sum(r["amount"] for r in subs if r["active"])
    t_bills= sum(r["amount"] for r in bills)
    t_debt = sum(r["monthly_payment"] for r in debts)
    t_gasto= t_fix + cc + t_ext + t_subs + t_bills
    sobra  = t_inc - t_gasto - t_debt

    paid_set = {(p["item_type"], p["item_id"]) for p in pays if p["paid"]}
    t_paid = sum(p["amount"] for p in pays if p["paid"])
    t_pend = (t_gasto + t_debt) - t_paid

    cor = "#16a34a" if sobra >= 0 else "#ef4444"
    st.markdown(f"""<div style="display:flex;align-items:center;justify-content:space-between;padding:6px 0 14px">
      <div><h1 style="font-size:26px;font-weight:700;color:#1a2332;margin:0">Oi, Família Peixoto! 👋</h1>
      <p style="color:#6b7280;font-size:13px;margin-top:3px">Painel de {ML(month)}</p></div>
      <div style="display:flex;gap:8px">
        <div style="text-align:center;padding:8px 14px;background:#f0fdf4;border-radius:10px;border:1px solid #bbf7d0"><div style="font-size:9px;text-transform:uppercase;letter-spacing:1px;color:#16a34a">Pago</div><div style="font-size:16px;font-weight:700;color:#16a34a;font-family:DM Mono,monospace">{R(t_paid)}</div></div>
        <div style="text-align:center;padding:8px 14px;background:#fff7ed;border-radius:10px;border:1px solid #fed7aa"><div style="font-size:9px;text-transform:uppercase;letter-spacing:1px;color:#ea580c">A pagar</div><div style="font-size:16px;font-weight:700;color:#ea580c;font-family:DM Mono,monospace">{R(t_pend)}</div></div>
        <div style="text-align:center;padding:8px 14px;background:{"#f0fdf4" if sobra>=0 else "#fef2f2"};border-radius:10px;border:1px solid {"#bbf7d0" if sobra>=0 else "#fecaca"}"><div style="font-size:9px;text-transform:uppercase;letter-spacing:1px;color:{cor}">Saldo</div><div style="font-size:16px;font-weight:700;color:{cor};font-family:DM Mono,monospace">{R(sobra)}</div></div>
      </div></div>""", unsafe_allow_html=True)

    cols = st.columns(4, gap="small")
    with cols[0]: st.markdown(f'<div class="mc"><div class="mc-val" style="color:#16a34a">{R(t_inc)}</div><div class="mc-label">Renda total</div></div>', unsafe_allow_html=True)
    with cols[1]: st.markdown(f'<div class="mc"><div class="mc-val" style="color:#ef4444">{R(t_gasto+t_debt)}</div><div class="mc-label">Total saídas</div></div>', unsafe_allow_html=True)
    with cols[2]: st.markdown(f'<div class="mc"><div class="mc-val" style="color:#3b82f6">{R(ef)}</div><div class="mc-label">Reserva</div></div>', unsafe_allow_html=True)
    with cols[3]: st.markdown(f'<div class="mc"><div class="mc-val" style="color:#8b5cf6">{R(t_inv)}</div><div class="mc-label">Investido total</div></div>', unsafe_allow_html=True)
    st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)

    left, right = st.columns([1.1,1], gap="medium")
    with left:
        # Entradas
        st.markdown('<div class="card card-green">', unsafe_allow_html=True)
        st.markdown('<div class="sec">Entradas</div>', unsafe_allow_html=True)
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
                    db.del_income(r["id"]); _mutated()
                if st.session_state.get(f"ei{r['id']}"):
                    with st.form(f"eif{r['id']}"):
                        nl=st.text_input("Descrição",r["label"]); na=st.number_input("Valor",value=float(r["amount"]),step=10.)
                        nd=st.selectbox("Dia",[15,30],index=0 if r["due_day"]==15 else 1)
                        if st.form_submit_button("Salvar"):
                            db.update_income(r["id"],nl,na,nd); del st.session_state[f"ei{r['id']}"]; _mutated()
        with st.expander("+ Adicionar entrada"):
            with st.form("add_inc"):
                l=st.text_input("Descrição","",placeholder="Ex: Salário…"); a=st.number_input("Valor",min_value=0.,step=50.); d_=st.selectbox("Dia",[15,30])
                if st.form_submit_button("Adicionar"):
                    if l and a>0: db.add_income(month,l,a,d_); _mutated()
        st.markdown(f'<div style="display:flex;justify-content:space-between;padding:8px 0 0;border-top:1px solid var(--border);font-size:13px;font-weight:600"><span>Total</span><span style="color:#16a34a;font-family:DM Mono,monospace">{R(t_inc)}</span></div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # Reserva
        st.markdown('<div class="card card-blue">', unsafe_allow_html=True)
        st.markdown('<div class="sec">Reserva de Emergência</div>', unsafe_allow_html=True)
        ef_pct = (ef/ef_target*100) if ef_target>0 else 0
        mc = round(ef/t_gasto if t_gasto>0 else 0, 1)
        st.markdown(f'<div style="display:flex;justify-content:space-between;margin-bottom:4px"><span style="font-size:13px">Saldo</span><span style="font-family:DM Mono,monospace;color:#3b82f6;font-weight:600">{R(ef)}</span></div><div style="font-size:11px;color:#6b7280;margin-bottom:4px">Meta: {R(ef_target)} · Cobre {mc} meses</div>{prog_bar(ef_pct,"#3b82f6")}', unsafe_allow_html=True)
        with st.expander("Atualizar reserva"):
            with st.form("ef_form"):
                nb=st.number_input("Saldo (R$)",value=float(ef),step=100.); nt_=st.number_input("Meta (R$)",value=float(ef_target or t_gasto*6),step=500.)
                if st.form_submit_button("Salvar"):
                    db.set_ef(month,nb); db.set_config("ef_target",str(nt_)); _mutated()
        st.markdown('</div>', unsafe_allow_html=True)

        # Gráfico
        from collections import defaultdict
        cat_t = defaultdict(float)
        for r in fix:   cat_t[r["category"]] += r["amount"]
        for r in ext:   cat_t[r["category"]] += r["amount"]
        for r in bills: cat_t["Contas"]       += r["amount"]
        for r in subs:
            if r["active"]: cat_t["Assinaturas"] += r["amount"]
        if cc>0:   cat_t["Cartão"]      += cc
        if t_ins>0:cat_t["Seguros"]     += t_ins
        if inv_this>0: cat_t["Investimento"] += inv_this
        if cat_t:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown('<div class="sec">Onde vai meu dinheiro</div>', unsafe_allow_html=True)
            cp=["#00c896","#3b82f6","#f59e0b","#ef4444","#8b5cf6","#06b6d4","#ec4899","#84cc16","#f97316","#6b7280"]
            lp,vp=list(cat_t.keys()),list(cat_t.values())
            fig=go.Figure(go.Pie(labels=lp,values=vp,hole=0.5,marker_colors=cp[:len(lp)],textinfo="label+percent",textfont_size=11,hovertemplate="%{label}: R$ %{value:,.2f}<extra></extra>"))
            fig.update_layout(height=230,margin=dict(t=5,b=5,l=0,r=0),paper_bgcolor="white",showlegend=False,font_family="Inter")
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar":False})
            st.markdown('</div>', unsafe_allow_html=True)

    with right:
        # Gastos Fixos
        st.markdown('<div class="card card-red">', unsafe_allow_html=True)
        st.markdown('<div class="sec">Gastos Fixos</div>', unsafe_allow_html=True)
        for due in [15,30]:
            sub=[r for r in fix if r["due_day"]==due]
            if not sub: continue
            st.markdown(f'<div style="margin:4px 0 4px"><span class="badge b-{15 if due==15 else 30}">Dia {due}</span></div>', unsafe_allow_html=True)
            for r in sub:
                c1,c2,c3,c4=st.columns([3,2,1,1])
                c1.markdown(f'<div style="font-size:13px">{r["label"]}</div><span class="badge b-gray" style="font-size:9px">{r["category"]}</span>', unsafe_allow_html=True)
                c2.markdown(f'<span style="font-family:DM Mono,monospace;color:#ef4444;font-size:13px">{R(r["amount"])}</span>', unsafe_allow_html=True)
                if c3.button("✎",key=f"ef_{r['id']}"): st.session_state[f"ef_{r['id']}"]=True
                if c4.button("✕",key=f"df_{r['id']}"): db.del_fixed(r["id"]); _mutated()
                if st.session_state.get(f"ef_{r['id']}"):
                    with st.form(f"eff_{r['id']}"):
                        nl=st.text_input("Descrição",r["label"]); na=st.number_input("Valor",value=float(r["amount"]),step=5.)
                        nd=st.selectbox("Dia",[15,30],index=0 if r["due_day"]==15 else 1)
                        nc=st.selectbox("Categoria",CATS,index=CATS.index(r["category"]) if r["category"] in CATS else 0)
                        if st.form_submit_button("Salvar"):
                            db.update_fixed(r["id"],nl,na,nd,nc); del st.session_state[f"ef_{r['id']}"]; _mutated()
        for label,value,color in [("💳 Cartão",cc,"#f59e0b"),("📱 Assinaturas",t_subs,"#8b5cf6"),("🏠 Contas",t_bills,"#ef4444"),("📤 Extras",t_ext,"#6b7280"),("🛡️ Seguros",t_ins,"#3b82f6"),("📈 Investimento",inv_this,"#16a34a"),("⚠️ Dívidas/mês",t_debt,"#dc2626")]:
            if value>0:
                st.markdown(f'<div style="display:flex;justify-content:space-between;padding:5px 0;font-size:13px;border-top:1px dashed var(--border)"><span>{label}</span><span style="font-family:DM Mono,monospace;color:{color}">{R(value)}</span></div>', unsafe_allow_html=True)
        with st.expander("+ Adicionar gasto fixo"):
            with st.form("add_fix"):
                l=st.text_input("Descrição","",placeholder="Ex: Aluguel…"); a=st.number_input("Valor",min_value=0.,step=10.)
                d_=st.selectbox("Venc.",[15,30]); ca=st.selectbox("Categoria",CATS)
                if st.form_submit_button("Adicionar"):
                    if l and a>0: db.add_fixed(month,l,a,d_,ca); _mutated()
        st.markdown(f'<div style="display:flex;justify-content:space-between;padding:8px 0 0;border-top:1px solid var(--border);font-size:13px;font-weight:600"><span>Total saídas</span><span style="color:#ef4444;font-family:DM Mono,monospace">{R(t_gasto+t_debt)}</span></div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # Diagnóstico
        st.markdown('<div class="card">', unsafe_allow_html=True)
        cd1,cd2=st.columns([3,1])
        cd1.markdown('<div class="sec" style="margin-bottom:6px">Diagnóstico</div>', unsafe_allow_html=True)
        api_d = os.environ.get("ANTHROPIC_API_KEY","") or cfg.get("api_key","")
        try: api_d = api_d or st.secrets.get("ANTHROPIC_API_KEY","")
        except Exception: pass
        if cd2.button("🔄",key="btn_diag",help="Atualizar IA"):
            _run_diag(api_d,month,t_inc,t_gasto,t_debt,ef,ext,fix,subs,debts)
        pct_g=(t_gasto+t_debt)/t_inc*100 if t_inc>0 else 0
        ef_m2=round(ef/t_gasto,1) if t_gasto>0 else 0
        total_dv=sum(r["remaining_amount"] for r in debts)
        if t_inc>0:
            if pct_g<=70:   st.markdown(f'<div class="diag-ok">✅ Gastos: {pct_g:.0f}% da renda</div>', unsafe_allow_html=True)
            elif pct_g<=90: st.markdown(f'<div class="diag-warn">⚠️ Gastos: {pct_g:.0f}% — acima do ideal</div>', unsafe_allow_html=True)
            else:           st.markdown(f'<div class="diag-crit">🚨 Gastos: {pct_g:.0f}% — situação crítica!</div>', unsafe_allow_html=True)
        if ef_m2>=6:   st.markdown(f'<div class="diag-ok">✅ Reserva: {ef_m2} meses</div>', unsafe_allow_html=True)
        elif ef_m2>=3: st.markdown(f'<div class="diag-warn">⚠️ Reserva: {ef_m2} meses (meta: 6)</div>', unsafe_allow_html=True)
        elif ef>0:     st.markdown(f'<div class="diag-crit">🚨 Reserva: apenas {ef_m2} meses</div>', unsafe_allow_html=True)
        if total_dv==0:          st.markdown('<div class="diag-ok">✅ Sem dívidas!</div>', unsafe_allow_html=True)
        elif total_dv<t_inc*3:   st.markdown(f'<div class="diag-warn">⚠️ Dívidas: {R(total_dv)}</div>', unsafe_allow_html=True)
        else:                    st.markdown(f'<div class="diag-crit">🚨 Dívidas: {R(total_dv)}</div>', unsafe_allow_html=True)
        dk=f"diag_{month}"
        if dk in st.session_state:
            st.markdown(f'<div style="background:#f8fafc;border-left:3px solid #00c896;border-radius:8px;padding:10px 14px;margin-top:6px;font-size:13px;line-height:1.7">{st.session_state[dk].replace(chr(10),"<br>")}</div>', unsafe_allow_html=True)
        else:
            st.markdown('<p style="color:#9ca3af;font-size:11px;margin-top:4px">Clique 🔄 para análise personalizada</p>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        if goals:
            st.markdown('<div class="card card-green">', unsafe_allow_html=True)
            st.markdown('<div class="sec">Metas</div>', unsafe_allow_html=True)
            for g in goals[:3]:
                pct=(g["current_amount"]/g["target_amount"]*100) if g["target_amount"]>0 else 0
                st.markdown(f'<div style="margin-bottom:8px"><div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:2px"><span style="font-weight:500">{g["label"]}</span><span style="color:#6b7280">{R(g["current_amount"])} / {R(g["target_amount"])}</span></div>{prog_bar(pct)}</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

    # Fluxo por ciclo
    _tab_fluxo_ciclos(month, d)


def _run_diag(api_key, month, t_inc, t_gasto, t_debt, ef, ext, fix, subs, debts):
    if not api_key:
        st.warning("Configure a chave API em ⚙️ Configurações."); return
    import anthropic as _ant
    from collections import defaultdict
    cat_g=defaultdict(float)
    for r in fix:  cat_g[r["category"]]+=r["amount"]
    for r in ext:  cat_g[r["category"]]+=r["amount"]
    for r in subs:
        if r["active"]: cat_g[r["category"]]+=r["amount"]
    cat_txt="\n".join([f"  · {k}: R${v:.0f}" for k,v in sorted(cat_g.items(),key=lambda x:-x[1])])
    total_debt=sum(r["remaining_amount"] for r in debts)
    sobra=t_inc-t_gasto-t_debt
    pct=(t_gasto/t_inc*100) if t_inc>0 else 0
    ef_m=round(ef/t_gasto,1) if t_gasto>0 else 0
    prompt=f"MES: {ML(month)} | Renda: R${t_inc:.0f} | Gastos: R${t_gasto:.0f} ({pct:.0f}%) | Sobra: R${sobra:.0f}\nReserva: R${ef:.0f} ({ef_m} meses) | Dividas: R${total_debt:.0f}\nGastos:\n{cat_txt}"
    system="Consultor financeiro da família Peixoto, direto e afetuoso. 3-4 linhas personalizadas. Se gastaram muito numa categoria: diga o valor e dê dica. Se têm sobra: sugira algo positivo. 'Vocês', valores reais, texto corrido, português informal."
    client=_ant.Anthropic(api_key=api_key)
    with st.spinner("Analisando..."):
        try:
            r=client.messages.create(model="claude-haiku-4-5-20251001",max_tokens=300,system=system,messages=[{"role":"user","content":prompt}])
            st.session_state[f"diag_{month}"]=r.content[0].text; st.rerun()
        except Exception as e: st.error(f"Erro: {e}")


def _fluxo_ciclo(month, d, ciclo):
    inc=d["income"]; fix=d["fixed"]; bills=d["bills"]; subs=d["subs"]
    cc_all=d["cc_all"]; debts=d["debts"]; invs=d["investments"]; ins=d["insurance"]
    cc_total=db.cc_total_from_data(cc_all, month)

    def _in(day): return day<=15 if ciclo==15 else day>15

    renda_items=[r for r in inc if r["due_day"]==ciclo]
    t_renda=sum(r["amount"] for r in renda_items)
    gasto_items=[]
    for r in fix:
        if _in(r["due_day"]): gasto_items.append(("fixed",r["id"],r["label"],r["amount"],r["due_day"],"Gasto Fixo",r["category"]))
    for r in bills:
        if _in(r["due_day"]): gasto_items.append(("bill",r["id"],r["label"],r["amount"],r["due_day"],"Conta",r["category"]))
    for r in subs:
        if r["active"] and _in(r["billing_day"]): gasto_items.append(("sub",r["id"],r["label"],r["amount"],r["billing_day"],"Assinatura",r["category"]))
    if ciclo==30 and cc_total>0:
        gasto_items.append(("cc_total",0,"Cartão de Crédito",cc_total,30,"Cartão",""))
    for debt in debts:
        dd=debt.get("due_day",30)
        if _in(dd): gasto_items.append(("debt",debt["id"],debt["label"],debt["monthly_payment"],dd,"Dívida",""))
    for i in ins:
        dd=i.get("due_day",30)
        if _in(dd): gasto_items.append(("ins",i["id"],f"Seguro: {i['label']}",i["monthly_cost"],dd,"Seguro",""))
    inv_this=next((r for r in invs if r["month"]==month),None)
    if inv_this:
        dd=inv_this.get("due_day",30)
        if _in(dd): gasto_items.append(("inv",inv_this["id"],f"Investimento ({inv_this['investment_type']})",float(inv_this["amount_added"]),dd,"Investimento",""))
    t_gastos=sum(x[3] for x in gasto_items)
    return t_renda, t_gastos, t_renda-t_gastos, renda_items, gasto_items


def _tab_fluxo_ciclos(month, d):
    st.markdown("---")
    st.markdown('<div class="sec" style="font-size:13px;margin-bottom:12px">💡 Fluxo de Caixa por Ciclo</div>', unsafe_allow_html=True)
    r15,g15,s15,ri15,gi15=_fluxo_ciclo(month,d,15)
    r30,g30,s30,ri30,gi30=_fluxo_ciclo(month,d,30)
    c1,c2,c3,c4,c5,c6=st.columns(6,gap="small")
    c1.markdown(f'<div class="mc"><div style="font-size:9px;color:#1d4ed8;font-weight:600;text-transform:uppercase;letter-spacing:1px;margin-bottom:3px">Renda dia 15</div><div style="font-size:16px;font-weight:700;color:#16a34a;font-family:DM Mono,monospace">{R(r15)}</div></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="mc"><div style="font-size:9px;color:#1d4ed8;font-weight:600;text-transform:uppercase;letter-spacing:1px;margin-bottom:3px">Gastos até 15</div><div style="font-size:16px;font-weight:700;color:#ef4444;font-family:DM Mono,monospace">{R(g15)}</div></div>', unsafe_allow_html=True)
    cor15="#16a34a" if s15>=0 else "#ef4444"
    c3.markdown(f'<div class="mc" style="border-top:3px solid {cor15}"><div style="font-size:9px;color:#6b7280;font-weight:600;text-transform:uppercase;letter-spacing:1px;margin-bottom:3px">Sobra dia 15</div><div style="font-size:16px;font-weight:700;color:{cor15};font-family:DM Mono,monospace">{R(s15)}</div></div>', unsafe_allow_html=True)
    c4.markdown(f'<div class="mc"><div style="font-size:9px;color:#7c3aed;font-weight:600;text-transform:uppercase;letter-spacing:1px;margin-bottom:3px">Renda dia 30</div><div style="font-size:16px;font-weight:700;color:#16a34a;font-family:DM Mono,monospace">{R(r30)}</div></div>', unsafe_allow_html=True)
    c5.markdown(f'<div class="mc"><div style="font-size:9px;color:#7c3aed;font-weight:600;text-transform:uppercase;letter-spacing:1px;margin-bottom:3px">Gastos dia 30</div><div style="font-size:16px;font-weight:700;color:#ef4444;font-family:DM Mono,monospace">{R(g30)}</div></div>', unsafe_allow_html=True)
    cor30="#16a34a" if s30>=0 else "#ef4444"
    c6.markdown(f'<div class="mc" style="border-top:3px solid {cor30}"><div style="font-size:9px;color:#6b7280;font-weight:600;text-transform:uppercase;letter-spacing:1px;margin-bottom:3px">Sobra dia 30</div><div style="font-size:16px;font-weight:700;color:{cor30};font-family:DM Mono,monospace">{R(s30)}</div></div>', unsafe_allow_html=True)
    st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
    tab_c15,tab_c30=st.tabs(["📅 Ciclo Dia 15","📅 Ciclo Dia 30"])
    type_colors={"Gasto Fixo":"b-15","Conta":"b-red","Cartão":"b-amber","Assinatura":"b-blue","Dívida":"b-red","Seguro":"b-blue","Investimento":"b-green"}
    for tab_c,ciclo,renda_items,gasto_items,t_renda,t_gastos,sobra in [(tab_c15,15,ri15,gi15,r15,g15,s15),(tab_c30,30,ri30,gi30,r30,g30,s30)]:
        with tab_c:
            left,right=st.columns([1,1],gap="medium")
            with left:
                st.markdown('<div class="card card-green">', unsafe_allow_html=True)
                st.markdown(f'<div class="sec">Renda — Dia {ciclo}</div>', unsafe_allow_html=True)
                if renda_items:
                    for r in renda_items:
                        st.markdown(f'<div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--border);font-size:13px"><span>{r["label"]}</span><span style="font-family:DM Mono,monospace;color:#16a34a">{R(r["amount"])}</span></div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<p style="color:#6b7280;font-size:13px">Nenhuma renda para o dia {ciclo}.</p>', unsafe_allow_html=True)
                st.markdown(f'<div style="display:flex;justify-content:space-between;padding:8px 0 0;border-top:1px solid var(--border);font-size:13px;font-weight:600"><span>Total renda</span><span style="color:#16a34a;font-family:DM Mono,monospace">{R(t_renda)}</span></div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)
            with right:
                st.markdown('<div class="card card-red">', unsafe_allow_html=True)
                st.markdown(f'<div class="sec">Contas — Ciclo Dia {ciclo}</div>', unsafe_allow_html=True)
                other=30 if ciclo==15 else 15
                for (itype,iid,ilabel,iamt,iday,icat,isubcat) in gasto_items:
                    badge=type_colors.get(icat,"b-gray")
                    c1_,c2_,c3_=st.columns([3.5,1.5,0.8])
                    c1_.markdown(f'<div style="font-size:12px;font-weight:500">{ilabel}</div><span class="badge {badge}" style="font-size:9px">{icat}</span>', unsafe_allow_html=True)
                    c2_.markdown(f'<span style="font-family:DM Mono,monospace;color:#ef4444;font-size:13px">{R(iamt)}</span>', unsafe_allow_html=True)
                    can_move=itype in ("fixed","bill","sub","debt","ins","inv")
                    if can_move and iid:
                        if c3_.button(f"→{other}",key=f"mv_{itype}_{iid}_{ciclo}"):
                            if itype=="fixed":   db.update_fixed(iid,ilabel,iamt,other,isubcat or "Outros")
                            elif itype=="bill":  db.upsert_bill(month,ilabel,iamt,isubcat or "Utilidades",other)
                            elif itype=="sub":   db.update_sub_billing_day(iid,other)
                            elif itype=="debt":  db.update_debt_due_day(iid,other)
                            elif itype=="ins":   db.update_insurance_due_day(iid,other)
                            elif itype=="inv":   db._exec("UPDATE investments SET due_day=%s WHERE id=%s",(other,iid))
                            _mutated()
                st.markdown(f'<div style="display:flex;justify-content:space-between;padding:8px 0 0;border-top:1px solid var(--border);font-size:13px;font-weight:600"><span>Total gastos</span><span style="color:#ef4444;font-family:DM Mono,monospace">{R(t_gastos)}</span></div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)
            cor_s="#16a34a" if sobra>=0 else "#ef4444"
            bg="#f0fdf4" if sobra>=0 else "#fef2f2"
            bdr="#bbf7d0" if sobra>=0 else "#fecaca"
            st.markdown(f'<div style="background:{bg};border:1px solid {bdr};border-top:3px solid {cor_s};border-radius:12px;padding:14px 18px;display:flex;justify-content:space-between;align-items:center"><div><div style="font-size:9px;text-transform:uppercase;letter-spacing:2px;color:{cor_s};margin-bottom:4px">{"✅" if sobra>=0 else "⚠️"} Sobra do ciclo dia {ciclo}</div><div style="font-size:11px;color:{cor_s};opacity:.8">{R(t_renda)} renda — {R(t_gastos)} gastos</div></div><div style="font-size:24px;font-weight:700;color:{cor_s};font-family:DM Mono,monospace">{R(sobra)}</div></div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# CONTAS FIXAS
# ══════════════════════════════════════════════════════════════════════════════
def tab_contas(month, d):
    bills     = d["bills"]
    templates = d["bill_templates"]
    # Gera contas dos modelos se ainda não existirem
    if db.generate_bills_from_templates(month, bills, templates) > 0:
        _mutated()
    t_bills = sum(r["amount"] for r in bills)
    pays    = d["payments"]
    st.markdown(f'<div style="display:flex;justify-content:space-between;align-items:center;padding:6px 0 14px"><div><h2 style="font-size:20px;font-weight:700;color:#1a2332;margin:0">Contas Fixas</h2><p style="color:#6b7280;font-size:12px;margin:3px 0 0">Água, luz, telefone, internet</p></div><div style="font-size:20px;font-weight:700;color:#ef4444;font-family:DM Mono,monospace">{R(t_bills)}</div></div>', unsafe_allow_html=True)
    left,right=st.columns([1.3,1],gap="medium")
    with left:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown(f'<div class="sec">Contas de {ML(month)}</div>', unsafe_allow_html=True)
        if bills:
            for r in bills:
                paid=db.is_paid_fast(pays,month,"bill",r["id"])
                c1,c2,c3,c4=st.columns([2.5,1.8,1,0.8])
                c1.markdown(f'<div style="padding-top:4px;font-size:13px;{"text-decoration:line-through;color:#9ca3af" if paid else ""}"><b>{r["label"]}</b><br><span class="badge b-gray" style="font-size:9px">{r["category"]} · dia {r["due_day"]}</span></div>', unsafe_allow_html=True)
                nv=c2.number_input("",value=float(r["amount"]),step=1.,key=f"bv{r['id']}",label_visibility="collapsed")
                if c3.button("💾",key=f"bs{r['id']}"):
                    db.upsert_bill(month,r["label"],nv,r["category"],r["due_day"]); _mutated()
                if c4.button("✅" if paid else "⬜",key=f"bp{r['id']}"):
                    db.set_payment(month,"bill",r["id"],r["label"],r["amount"],not paid); _mutated()
            st.markdown(f'<div style="display:flex;justify-content:space-between;padding:8px 0 0;border-top:1px solid var(--border);font-size:13px;font-weight:600"><span>Total</span><span style="color:#ef4444;font-family:DM Mono,monospace">{R(t_bills)}</span></div>', unsafe_allow_html=True)
        else:
            st.markdown('<p style="color:#6b7280;font-size:13px">Nenhuma conta. Adicione modelos →</p>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        if templates:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown('<div class="sec">Modelos recorrentes</div>', unsafe_allow_html=True)
            for t in templates:
                c1,c2,c3=st.columns([3,2,1])
                c1.markdown(f'<span style="font-size:13px">{t["label"]}</span><br><span class="badge b-gray">{t["category"]}</span>', unsafe_allow_html=True)
                c2.markdown(f'<span style="font-size:12px;color:#6b7280">~{R(t["estimated_amount"])} · dia {t["due_day"]}</span>', unsafe_allow_html=True)
                if c3.button("✕",key=f"dtpl{t['id']}"): db.del_bill_template(t["id"]); _mutated()
            st.markdown('</div>', unsafe_allow_html=True)
    with right:
        st.markdown('<div class="card card-red">', unsafe_allow_html=True)
        st.markdown('<div class="sec">Lançar conta este mês</div>', unsafe_allow_html=True)
        with st.form("add_bm"):
            l=st.text_input("Conta","",placeholder="Ex: Conta de Luz"); a=st.number_input("Valor (R$)",min_value=0.,step=1.)
            ca=st.selectbox("Categoria",["Utilidades","Moradia","Comunicação","Outros"])
            dd=st.number_input("Dia venc.",min_value=1,max_value=31,value=10)
            if st.form_submit_button("Adicionar",use_container_width=True):
                if l and a>0: db.upsert_bill(month,l,a,ca,int(dd)); _mutated()
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="sec">Criar modelo recorrente</div>', unsafe_allow_html=True)
        with st.form("add_tpl"):
            l=st.text_input("Nome","",placeholder="Ex: Conta de Água"); a=st.number_input("Estimativa (R$)",min_value=0.,step=5.)
            ca=st.selectbox("Categoria",["Utilidades","Moradia","Comunicação","Outros"])
            dd=st.number_input("Dia",min_value=1,max_value=31,value=10)
            if st.form_submit_button("Criar",use_container_width=True):
                if l: db.add_bill_template(l,a,ca,int(dd)); _mutated()
        st.markdown('</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PLANILHA
# ══════════════════════════════════════════════════════════════════════════════
def tab_planilha(month, d):
    inc   = d["income"];  fix=d["fixed"];  bills=d["bills"]
    cc_its= db.cc_items_from_data(d["cc_all"],month)
    subs  = [r for r in d["subs"] if r["active"]]
    ext   = d["extras"]; debts=d["debts"]; ins=d["insurance"]
    invs  = d["investments"]; pays=d["payments"]
    inv_this=next((r for r in invs if r["month"]==month),None)
    t_inc =sum(r["amount"] for r in inc)
    all_exp=[]
    for r in fix:    all_exp.append(("fixed",r["id"],r["label"],r["amount"],r["due_day"],"Gasto Fixo"))
    for r in bills:  all_exp.append(("bill",r["id"],r["label"],r["amount"],r["due_day"],"Conta"))
    for it in cc_its:all_exp.append(("cc",it["id"],f"{it['label']} ({it['installment']})",it["monthly"],30,"Cartão"))
    for r in subs:   all_exp.append(("sub",r["id"],r["label"],r["amount"],r["billing_day"],"Assinatura"))
    for r in ext:    all_exp.append(("ext",r["id"],r["label"],r["amount"],0,"Saída"))
    for debt in debts: all_exp.append(("debt",debt["id"],debt["label"],debt["monthly_payment"],debt.get("due_day",30),"Dívida"))
    for i in ins:    all_exp.append(("ins",i["id"],f"Seguro: {i['label']}",i["monthly_cost"],i.get("due_day",30),"Seguro"))
    if inv_this:     all_exp.append(("inv",inv_this["id"],f"Investimento ({inv_this['investment_type']})",float(inv_this["amount_added"]),inv_this.get("due_day",30),"Investimento"))
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
    type_colors={"Gasto Fixo":"b-15","Conta":"b-red","Cartão":"b-amber","Assinatura":"b-blue","Saída":"b-gray","Dívida":"b-red","Seguro":"b-blue","Investimento":"b-green"}
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
                db.set_payment(month,itype,iid,ilabel,iamt,not paid); _mutated()
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
                db.set_payment(month,"income",r["id"],r["label"],r["amount"],not paid); _mutated()
        st.markdown(f'<div style="display:flex;justify-content:space-between;padding:8px 0 0;border-top:1px solid var(--border);font-size:13px;font-weight:600"><span>Total</span><span style="font-family:DM Mono,monospace;color:#16a34a">{R(t_inc)}</span></div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        sobra=t_inc-t_exp
        st.markdown(f'<div class="card" style="text-align:center;border-top:3px solid {"#16a34a" if sobra>=0 else "#ef4444"}"><div style="font-size:10px;text-transform:uppercase;letter-spacing:1.5px;color:#6b7280;margin-bottom:5px">Resultado</div><div style="font-size:24px;font-weight:700;font-family:DM Mono,monospace;color:{"#16a34a" if sobra>=0 else "#ef4444"}">{R(sobra)}</div></div>', unsafe_allow_html=True)
        pct_pago=(t_paid/t_exp*100) if t_exp>0 else 0
        st.markdown(f'<div class="card"><div class="sec">Progresso</div><div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:4px"><span style="color:#16a34a">Pago: {R(t_paid)}</span><span style="color:#ea580c">Pendente: {R(t_pend)}</span></div>{prog_bar(pct_pago)}<div style="font-size:10px;color:#6b7280;margin-top:3px">{pct_pago:.0f}% pago</div></div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# VARIÁVEL
# ══════════════════════════════════════════════════════════════════════════════
def tab_variavel(month, d):
    sub1,sub2,sub3,sub4=st.tabs(["💳 Cartão","🎬 Saídas","💸 Gastos Extras","📱 Assinaturas"])
    cc_all=d["cc_all"]; subs=d["subs"]; cfg=d["config"]
    items_m=db.cc_items_from_data(cc_all,month)
    total_m=db.cc_total_from_data(cc_all,month)
    extras=d["extras"]
    api_key=os.environ.get("ANTHROPIC_API_KEY","") or cfg.get("api_key","")
    try: api_key=api_key or st.secrets.get("ANTHROPIC_API_KEY","")
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
                    if c3.button("✕",key=f"dcc{it['id']}"): db.del_cc(it["id"]); _mutated()
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
                if st.form_submit_button("Adicionar",use_container_width=True):
                    if l and a>0: db.add_cc(l,a,int(n),sm,cn); _mutated()
            a_val=st.session_state.get("cc_valor",0.0); n_val=st.session_state.get("cc_parcelas",1)
            if n_val>1 and a_val>0:
                st.markdown(f'<div style="padding:8px 12px;background:#fffbeb;border-radius:8px;font-size:12px;color:#92400e;margin-top:4px">{int(n_val)}× de {R(a_val/n_val)}</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown('<div class="sec">Colar Fatura (IA)</div>', unsafe_allow_html=True)
            fatura=st.text_area("Texto da fatura","",height=100,placeholder="Cole aqui…",key="fatura_txt")
            card_n=st.text_input("Cartão","Cartão Principal",key="fatura_card")
            if st.button("Processar com IA",key="proc_f",use_container_width=True):
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
                        if c3.button("✕",key=f"des{r['id']}"): db.del_extra(r["id"]); _mutated()
            else:
                st.markdown('<p style="color:#6b7280;font-size:13px">Nenhuma saída.</p>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
        with right:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown('<div class="sec">Registrar saída</div>', unsafe_allow_html=True)
            with st.form("add_saida"):
                l=st.text_input("Descrição","",placeholder="Ex: Cinema, Restaurante…"); a=st.number_input("Valor (R$)",min_value=0.,step=5.)
                ca=st.selectbox("Categoria",CATS); pm=st.selectbox("Pagamento",PAY)
                if st.form_submit_button("Registrar",use_container_width=True):
                    if l and a>0: db.add_extra(month,l,a,ca,pm,"saida"); _mutated()
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
                    if st.button("✕",key=f"dex{r['id']}"): db.del_extra(r["id"]); _mutated()
            else:
                st.markdown('<p style="color:#6b7280;font-size:13px">Nenhum gasto.</p>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
        with right:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown('<div class="sec">Registrar</div>', unsafe_allow_html=True)
            with st.form("add_extra"):
                l=st.text_input("Descrição","",placeholder="Ex: Padaria, Farmácia…"); a=st.number_input("Valor (R$)",min_value=0.,step=5.)
                ca=st.selectbox("Categoria",CATS); pm=st.selectbox("Método",["PIX","Dinheiro","Transferência","Débito","Outro"])
                if st.form_submit_button("Registrar",use_container_width=True):
                    if l and a>0: db.add_extra(month,l,a,ca,pm,"extra"); _mutated()
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
                    if c2.button("⏸" if r["active"] else "▶",key=f"ts{r['id']}"): db.toggle_sub(r["id"]); _mutated()
                    if c3.button("✕",key=f"ds{r['id']}"): db.del_sub(r["id"]); _mutated()
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
                if st.form_submit_button("Adicionar",use_container_width=True):
                    if l and a>0: db.add_sub(l,a,ca,int(bd)); _mutated()
            st.markdown('</div>', unsafe_allow_html=True)


def _parse_fatura(api_key, text, month, card_name):
    import anthropic as _ant
    system='Analise a fatura e retorne APENAS JSON array: [{"label":"item","total_amount":valor,"installments":1,"start_month":"AAAA-MM"}]. Para parceladas total_amount é o total. Sem explicações.'
    try:
        client=_ant.Anthropic(api_key=api_key)
        r=client.messages.create(model="claude-haiku-4-5-20251001",max_tokens=1000,system=system,messages=[{"role":"user","content":f"Fatura {month}:\n{text}"}])
        raw=r.content[0].text.strip().replace("```json","").replace("```","").strip()
        items=json.loads(raw); count=0
        for it in items:
            if "label" in it and "total_amount" in it:
                db.add_cc(it["label"],float(it["total_amount"]),int(it.get("installments",1)),it.get("start_month",month),card_name); count+=1
        st.success(f"✅ {count} item(s) importado(s)!"); _mutated()
    except Exception as e: st.error(f"Erro: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# INVESTIMENTOS & SEGUROS
# ══════════════════════════════════════════════════════════════════════════════
def tab_investimentos(month, d):
    invs=d["investments"]; ins=d["insurance"]; cfg=d["config"]
    annual_rate=float(cfg.get("inv_rate","12") or 12)
    monthly_contrib=float(cfg.get("inv_contrib","0") or 0)
    current_total=db.investment_last_total(invs)
    sub_inv,sub_seg=st.tabs(["📈 Investimentos","🛡️ Seguros"])
    with sub_inv:
        cols=st.columns(4,gap="small")
        with cols[0]: st.markdown(f'<div class="mc"><div class="mc-val" style="color:#16a34a">{R(current_total)}</div><div class="mc-label">Total acumulado</div></div>', unsafe_allow_html=True)
        for idx,(yr,col) in enumerate([(5,"#3b82f6"),(10,"#8b5cf6"),(20,"#f59e0b")]):
            with cols[idx+1]:
                pv=db.investment_projection(current_total,monthly_contrib,annual_rate,yr)
                st.markdown(f'<div class="mc"><div class="mc-val" style="color:{col}">{R(pv)}</div><div class="mc-label">Projeção {yr} anos</div></div>', unsafe_allow_html=True)
        st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)
        fig=go.Figure()
        if invs:
            fig.add_trace(go.Bar(name="Acumulado",x=[ML(r["month"]) for r in invs],y=[r["total_accumulated"] for r in invs],marker_color="#00c896",text=[R(r["total_accumulated"]) for r in invs],textposition="outside",textfont_size=9))
        for yr,col in [(5,"#3b82f6"),(10,"#8b5cf6"),(15,"#f59e0b"),(20,"#ef4444")]:
            pv=db.investment_projection(current_total,monthly_contrib,annual_rate,yr)
            fig.add_trace(go.Bar(name=f"{yr} anos",x=[f"→ {yr} anos"],y=[pv],marker_color=col,text=[R(pv)],textposition="outside",textfont_size=9))
        fig.update_layout(height=280,paper_bgcolor="white",plot_bgcolor="white",margin=dict(t=20,b=20,l=0,r=0),legend=dict(orientation="h",y=-0.2,font_size=11),xaxis=dict(tickfont_size=10,gridcolor="#f3f4f6"),yaxis=dict(tickfont_size=10,gridcolor="#f3f4f6",tickformat=",.0f"),font_family="Inter",barmode="group")
        st.plotly_chart(fig,use_container_width=True,config={"displayModeBar":False})
        left,right=st.columns([1.2,1],gap="medium")
        with left:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown('<div class="sec">Histórico</div>', unsafe_allow_html=True)
            if invs:
                st.markdown('<table class="tbl"><thead><tr><th>Mês</th><th>Aportado</th><th>Origem</th><th>Total</th><th>Tipo</th></tr></thead><tbody>', unsafe_allow_html=True)
                for r in reversed(invs):
                    src='<span class="badge b-green">Renda</span>' if "Renda do mês" in r.get("investment_source","") else '<span class="badge b-blue">Guardado</span>'
                    st.markdown(f'<tr><td>{ML(r["month"])}</td><td style="font-family:DM Mono,monospace;color:#16a34a">{R(r["amount_added"])}</td><td>{src}</td><td style="font-family:DM Mono,monospace;font-weight:600">{R(r["total_accumulated"])}</td><td><span class="badge b-gray">{r["investment_type"]}</span></td></tr>', unsafe_allow_html=True)
                st.markdown('</tbody></table>', unsafe_allow_html=True)
                for r in invs:
                    if st.button(f"✕ {ML(r['month'])}",key=f"del_inv_{r['id']}"): db.del_investment(r["id"]); _mutated()
            else:
                st.markdown('<p style="color:#6b7280;font-size:13px">Nenhum aporte.</p>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
        with right:
            st.markdown('<div class="card card-green">', unsafe_allow_html=True)
            st.markdown('<div class="sec">Registrar Aporte</div>', unsafe_allow_html=True)
            with st.form("add_inv"):
                sm=st.text_input("Mês (AAAA-MM)",value=month); aad=st.number_input("Valor aportado (R$)",min_value=0.,step=100.)
                source=st.selectbox("Origem",["Renda do mês (salário/rendimento)","Renda guardada (já estava investida)"])
                ciclo_inv=st.selectbox("Ciclo",[30,15]); tp=st.selectbox("Tipo",["Renda Fixa","Tesouro Direto","CDB","LCI/LCA","FII","Ações","Previdência","Cripto","Outros"])
                auto_total=current_total+aad if "Renda do mês" in source else current_total
                if aad>0: st.info(f"Total calculado: {R(auto_total)}")
                override=st.number_input("Total acumulado real (R$)",value=float(auto_total),step=100.); nt_=st.text_input("Observações","")
                if st.form_submit_button("Salvar",use_container_width=True):
                    if aad>0: db.upsert_investment(sm,aad,float(override),tp,source,int(ciclo_inv),nt_); _mutated()
                    else: st.warning("Informe o valor.")
            st.markdown('</div>', unsafe_allow_html=True)
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown('<div class="sec">Parâmetros Projeção</div>', unsafe_allow_html=True)
            with st.form("inv_cfg"):
                nc=st.number_input("Aporte mensal planejado (R$)",value=float(monthly_contrib),step=100.)
                nr=st.number_input("Taxa anual esperada (%)",value=float(annual_rate),step=0.5)
                if st.form_submit_button("Atualizar",use_container_width=True):
                    db.set_config("inv_contrib",str(nc)); db.set_config("inv_rate",str(nr)); _mutated()
            st.markdown('</div>', unsafe_allow_html=True)

    with sub_seg:
        t_ins=db.insurance_total_from_data(ins)
        cols=st.columns(3,gap="small")
        with cols[0]: st.markdown(f'<div class="mc"><div class="mc-val" style="color:#3b82f6">{len(ins)}</div><div class="mc-label">Seguros ativos</div></div>', unsafe_allow_html=True)
        with cols[1]: st.markdown(f'<div class="mc"><div class="mc-val" style="color:#ef4444">{R(t_ins)}</div><div class="mc-label">Custo mensal</div></div>', unsafe_allow_html=True)
        with cols[2]: st.markdown(f'<div class="mc"><div class="mc-val" style="color:#f59e0b">{R(t_ins*12)}</div><div class="mc-label">Custo anual</div></div>', unsafe_allow_html=True)
        st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)
        pays=d["payments"]
        left,right=st.columns([1.3,1],gap="medium")
        with left:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown('<div class="sec">Seus Seguros</div>', unsafe_allow_html=True)
            if ins:
                for r in ins:
                    paid=db.is_paid_fast(pays,month,"ins",r["id"])
                    c1,c2,c3,c4=st.columns([3.5,1,0.8,0.8])
                    c1.markdown(f'<div style="padding:6px 0"><div style="font-weight:600;font-size:13px">{r["label"]} {"✅" if paid else ""}</div><div style="font-size:11px;color:#6b7280">🏦 {r["provider"] or "?"} · 🛡️ {r["coverage"] or "?"}</div><div style="font-family:DM Mono,monospace;font-weight:700;color:#ef4444;font-size:13px">{R(r["monthly_cost"])}/mês</div><span class="badge b-{"15" if r.get("due_day",30)==15 else "30"}" style="font-size:9px">Dia {r.get("due_day",30)}</span></div>', unsafe_allow_html=True)
                    if c2.button("✅" if paid else "⬜",key=f"pin{r['id']}"): db.set_payment(month,"ins",r["id"],r["label"],r["monthly_cost"],not paid); _mutated()
                    other_d=15 if r.get("due_day",30)==30 else 30
                    if c3.button(f"→{other_d}",key=f"mvin{r['id']}"): db.update_insurance_due_day(r["id"],other_d); _mutated()
                    if c4.button("✕",key=f"din{r['id']}"): db.del_insurance(r["id"]); _mutated()
            else:
                st.markdown('<p style="color:#6b7280;font-size:13px">Nenhum seguro.</p>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
        with right:
            st.markdown('<div class="card card-blue">', unsafe_allow_html=True)
            st.markdown('<div class="sec">Cadastrar Seguro</div>', unsafe_allow_html=True)
            with st.form("add_ins"):
                l=st.text_input("Tipo","",placeholder="Ex: Seguro de Vida"); tp_ins=st.selectbox("Categoria",["Vida","Saúde","Carro","Casa/Residencial","Viagem","Outros"])
                pv_=st.text_input("Seguradora","",placeholder="Ex: Bradesco Seguros"); ap=st.text_input("Nº Apólice",""); cv=st.text_input("Cobertura","",placeholder="Ex: R$ 500k")
                mc=st.number_input("Custo mensal (R$)",min_value=0.,step=10.); ciclo_seg=st.selectbox("Ciclo",[30,15]); nt_=st.text_input("Obs.","")
                if st.form_submit_button("Cadastrar",use_container_width=True):
                    if l and mc>0:
                        notes=f"Tipo: {tp_ins}"+(f" · Apólice: {ap}" if ap else "")+(f" · {nt_}" if nt_ else "")
                        db.add_insurance(l,pv_,mc,cv,int(ciclo_seg),notes); _mutated()
                    else: st.warning("Preencha nome e custo.")
            st.markdown('</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# DÍVIDAS
# ══════════════════════════════════════════════════════════════════════════════
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
                ciclo_badge=f'<span class="badge b-{"15" if r.get("due_day",30)==15 else "30"}" style="font-size:9px">Dia {r.get("due_day",30)}</span>'
                st.markdown(f'<div style="padding:10px 0;border-bottom:1px solid var(--border)"><div style="display:flex;justify-content:space-between;align-items:flex-start"><div><div style="font-weight:600;font-size:13px">{r["label"]} {ciclo_badge}</div><div style="font-size:11px;color:#6b7280">Restante: <b style="color:#ef4444">{R(r["remaining_amount"])}</b> · Parcela: {R(r["monthly_payment"])} · Juros: {r["interest_rate"]:.1f}%a.m.</div></div>{alert}</div>{prog_bar(pct)}</div>', unsafe_allow_html=True)
                ca,cb,cc_col=st.columns([1.5,0.7,0.7])
                nv=ca.number_input("Saldo",value=float(r["remaining_amount"]),step=100.,key=f"dr{r['id']}")
                if ca.button("Salvar",key=f"dsr{r['id']}"): db.update_debt_remaining(r["id"],nv); _mutated()
                other_d=15 if r.get("due_day",30)==30 else 30
                if cb.button(f"→{other_d}",key=f"mvd{r['id']}"): db.update_debt_due_day(r["id"],other_d); _mutated()
                if cc_col.button("✕",key=f"dd{r['id']}"): db.del_debt(r["id"]); _mutated()
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
            if st.form_submit_button("Cadastrar",use_container_width=True):
                if l and total>0 and mp>0: db.add_debt(l,total,rem or total,mp,ir,int(ciclo_d),nt_); _mutated()
                else: st.warning("Preencha os campos.")
        st.markdown('</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# METAS
# ══════════════════════════════════════════════════════════════════════════════
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
                if cb.button("Salvar",key=f"gs{g['id']}"): db.update_goal(g["id"],nv); _mutated()
                if cc_g.button("✕",key=f"gd{g['id']}"): db.del_goal(g["id"]); _mutated()
        else:
            st.markdown('<p style="color:#6b7280;font-size:13px">Nenhuma meta.</p>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    with right:
        st.markdown('<div class="card card-green">', unsafe_allow_html=True)
        st.markdown('<div class="sec">Cadastrar Meta</div>', unsafe_allow_html=True)
        with st.form("add_goal"):
            l=st.text_input("Meta","",placeholder="Ex: Viagem Europa…"); tg=st.number_input("Valor alvo (R$)",min_value=0.,step=500.)
            cur_g=st.number_input("Já tenho (R$)",min_value=0.,step=100.); dl=st.text_input("Prazo",""); nt_=st.text_input("Obs.","")
            if st.form_submit_button("Cadastrar",use_container_width=True):
                if l and tg>0: db.add_goal(l,tg,cur_g,dl,nt_); _mutated()
                else: st.warning("Preencha os campos.")
        st.markdown('</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# CONSULTOR IA
# ══════════════════════════════════════════════════════════════════════════════
def tab_assistente(month, d):
    st.markdown('<div style="text-align:center;padding:10px 0 20px"><h2 style="font-size:22px;font-weight:700;color:#1a2332;margin:0">Consultor Financeiro IA</h2><p style="color:#6b7280;font-size:13px;margin-top:5px">Análise direta — estilo <b>Bruno Perini</b> e <b>Thiago Nigro</b></p></div>', unsafe_allow_html=True)
    cfg=d["config"]; inc=d["income"]; fix=d["fixed"]; ext=d["extras"]; subs=d["subs"]
    debts=d["debts"]; invs=d["investments"]; goals=d["goals"]
    api_key=os.environ.get("ANTHROPIC_API_KEY","") or cfg.get("api_key","")
    try: api_key=api_key or st.secrets.get("ANTHROPIC_API_KEY","")
    except Exception: pass
    if not api_key: st.warning("Configure a chave API em ⚙️ Configurações."); return
    cc=db.cc_total_from_data(d["cc_all"],month); ef=d["ef"]
    t_inc=sum(r["amount"] for r in inc); t_fix=sum(r["amount"] for r in fix)
    t_ext=sum(r["amount"] for r in ext); t_subs=sum(r["amount"] for r in subs if r["active"])
    t_debt_m=sum(r["monthly_payment"] for r in debts); t_debt_t=sum(r["remaining_amount"] for r in debts)
    t_inv=db.investment_last_total(invs)
    _,c,_=st.columns([1,2,1])
    with c:
        if st.button("🔍 Analisar minha situação financeira",use_container_width=True):
            _run_ai_full(api_key,month,t_inc,t_fix,t_ext,t_subs,cc,t_debt_m,t_debt_t,t_inv,ef,goals,debts,subs,fix,inc)
    key=f"ai_{month}"
    if key in st.session_state:
        st.markdown(f'<div style="background:#f8fafc;border:1px solid #e5e7eb;border-left:4px solid #00c896;border-radius:12px;padding:22px 26px;margin-top:18px;font-size:14px;line-height:1.8;color:#374151;max-width:780px;margin-inline:auto">{st.session_state[key].replace(chr(10),"<br>")}</div>', unsafe_allow_html=True)
        qs=["Como pagar minhas dívidas mais rápido?","Quanto devo investir por mês?","Onde estou desperdiçando dinheiro?","Como montar minha reserva de emergência?"]
        qc=st.columns(2)
        for i,q in enumerate(qs):
            if qc[i%2].button(q,key=f"q{i}"):
                _run_ai_q(api_key,q,month,t_inc,t_fix+cc+t_subs+t_ext,t_debt_t,t_inv,ef)
    if f"ai_q_{month}" in st.session_state:
        st.markdown(f'<div style="background:white;border:1px solid #e5e7eb;border-radius:10px;padding:14px 18px;margin-top:10px;font-size:13px;line-height:1.7;max-width:780px;margin-inline:auto">{st.session_state[f"ai_q_{month}"].replace(chr(10),"<br>")}</div>', unsafe_allow_html=True)


def _run_ai_full(api_key,month,t_inc,t_fix,t_ext,t_subs,cc,t_debt_m,t_debt_t,t_inv,ef,goals,debts,subs,fix,inc):
    import anthropic as _ant
    g_txt="\n".join([f"  · {g['label']}: {R(g['current_amount'])}/{R(g['target_amount'])} ({g['deadline']})" for g in goals]) or "  Nenhuma"
    d_txt="\n".join([f"  · {d['label']}: R${d['remaining_amount']:.0f} rest, {R(d['monthly_payment'])}/mês, {d['interest_rate']:.1f}%a.m." for d in debts]) or "  Nenhuma"
    s_txt="\n".join([f"  · {s['label']}: {R(s['amount'])}/mês" for s in subs if s["active"]]) or "  Nenhuma"
    prompt=f"""DADOS — {ML(month)}: Renda: R${t_inc:.0f} | Gastos: R${t_fix+cc+t_subs+t_ext:.0f} ({((t_fix+cc+t_subs+t_ext)/t_inc*100 if t_inc>0 else 0):.0f}%) | Sobra: R${t_inc-t_fix-cc-t_subs-t_ext-t_debt_m:.0f}
Dívidas/mês: R${t_debt_m:.0f} | Total dívidas: R${t_debt_t:.0f} | Investido: R${t_inv:.0f} | Reserva: R${ef:.0f}
Assinaturas: {s_txt} | Dívidas: {d_txt} | Metas: {g_txt}"""
    system="Consultor financeiro da família Peixoto, estilo Bruno Perini/Primo Rico. Direto, focado em resultado.\nESTRUTURA: 1.📊 Diagnóstico (3 linhas) 2.🚨 Problemas (max 3, valores reais) 3.💡 Plano (5 ações priorizadas) 4.🎯 Meta do mês (1 ação AGORA) 5.📈 Em 12 meses\nMax 500 palavras. Português informal."
    client=_ant.Anthropic(api_key=api_key)
    with st.spinner("Analisando..."):
        try:
            r=client.messages.create(model="claude-opus-4-6",max_tokens=700,system=system,messages=[{"role":"user","content":prompt}])
            st.session_state[f"ai_{month}"]=r.content[0].text; st.rerun()
        except Exception as e: st.error(f"Erro: {e}")

def _run_ai_q(api_key,question,month,t_inc,t_gasto,t_debt,t_inv,ef):
    import anthropic as _ant
    ctx=f"Renda: R${t_inc:.0f} · Gastos: R${t_gasto:.0f} · Dívidas: R${t_debt:.0f} · Investido: R${t_inv:.0f} · Reserva: R${ef:.0f}"
    client=_ant.Anthropic(api_key=api_key)
    with st.spinner("..."):
        try:
            r=client.messages.create(model="claude-haiku-4-5-20251001",max_tokens=400,system="Consultor financeiro direto, estilo Bruno Perini. Max 200 palavras, prático. Português informal.",messages=[{"role":"user","content":f"Contexto: {ctx}\nPergunta: {question}"}])
            st.session_state[f"ai_q_{month}"]=r.content[0].text; st.rerun()
        except Exception as e: st.error(f"Erro: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURAÇÕES
# ══════════════════════════════════════════════════════════════════════════════
def tab_config(d):
    cfg=d["config"]
    st.markdown('<h2 style="font-size:20px;font-weight:700;color:#1a2332;margin:0 0 18px">Configurações</h2>', unsafe_allow_html=True)
    c1,c2=st.columns(2,gap="medium")
    with c1:
        st.markdown('<div class="card card-green">', unsafe_allow_html=True)
        st.markdown('<div class="sec">Alterar Senha</div>', unsafe_allow_html=True)
        with st.form("pwd"):
            cur_=st.text_input("Senha atual",type="password"); n1=st.text_input("Nova senha",type="password"); n2=st.text_input("Confirmar",type="password")
            if st.form_submit_button("Alterar",use_container_width=True):
                if not db.check_pwd(cur_): st.error("Senha incorreta.")
                elif n1!=n2: st.error("Senhas não coincidem.")
                elif len(n1)<4: st.error("Mínimo 4 caracteres.")
                else: db.change_pwd(n1); st.success("✅ Senha alterada.")
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="sec">Desfazer</div>', unsafe_allow_html=True)
        if st.button("↩ Desfazer última ação",use_container_width=True):
            ok,msg=db.undo_last(); (st.success if ok else st.warning)(msg); _mutated()
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="sec">Schema SQL (Supabase)</div>', unsafe_allow_html=True)
        st.code(db.SCHEMA_SQL,language="sql")
        st.markdown('</div>', unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="card card-green">', unsafe_allow_html=True)
        st.markdown('<div class="sec">Chave API Anthropic</div>', unsafe_allow_html=True)
        cur_k=cfg.get("api_key",""); masked=f"sk-…{cur_k[-6:]}" if cur_k else "não configurada"
        st.markdown(f'<p style="font-size:12px;color:#6b7280;margin-bottom:8px">Atual: <code>{masked}</code></p>', unsafe_allow_html=True)
        with st.form("api"):
            k=st.text_input("Nova chave","",placeholder="sk-ant-…")
            if st.form_submit_button("Salvar",use_container_width=True):
                if k.startswith("sk-"): db.set_api_key(k); st.success("✅ Salva."); _mutated()
                else: st.warning("Deve começar com 'sk-'")
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="sec">Banco de dados</div>', unsafe_allow_html=True)
        st.markdown('<div class="diag-ok">🟢 Supabase (Pooler) conectado<br><code style="font-size:10px">aws-0-sa-east-1.pooler.supabase.com:6543</code></div>', unsafe_allow_html=True)
        st.markdown(f'<div style="font-size:12px;color:#6b7280;line-height:2;margin-top:8px">Pool · <span style="color:#374151">2–10 conexões (ThreadedConnectionPool)</span><br>Cache · <span style="color:#374151">@st.cache_data TTL 8s por mês</span><br>Versão · <span style="color:#00c896;font-weight:600">9.0 — Performance Edition</span></div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        if st.button("🔄 Forçar reconexão",use_container_width=True):
            if "_pool" in st.session_state:
                try: st.session_state["_pool"].closeall()
                except Exception: pass
                del st.session_state["_pool"]
            st.cache_data.clear(); st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
def main():
    st.markdown(CSS, unsafe_allow_html=True)

    # ── Pool: inicializa uma vez por sessão ─────────────────────────────────
    if "_pool" not in st.session_state:
        with st.spinner("Conectando ao banco…"):
            ok, err = db.init_db()
        if not ok:
            st.error(f"**Erro de conexão:** {err}")
            st.markdown("""
            **Como corrigir:**
            1. Verifique `DB_PASSWORD` nos Secrets do Streamlit Cloud  
            2. Confirme que o host é `aws-0-sa-east-1.pooler.supabase.com`  
            3. Porta deve ser `6543` (pooler, não 5432)
            """)
            if st.button("🔄 Tentar reconectar"):
                st.rerun()
            return

    # ── Auth ────────────────────────────────────────────────────────────────
    if "auth" not in st.session_state:
        st.session_state.auth = False
    if not st.session_state.auth:
        try:
            t = st.query_params.get("t","")
            if t and _check_token(t): st.session_state.auth = True
        except Exception: pass
    if not st.session_state.auth:
        login_page(); return

    # ── Mês ─────────────────────────────────────────────────────────────────
    if "month" not in st.session_state:
        st.session_state.month = datetime.now().strftime("%Y-%m")
    month = sidebar(st.session_state.month)

    # ── Carrega dados em batch (cacheados 8s) ────────────────────────────────
    with st.spinner(""):
        d = _load(month)

    # ── Header ──────────────────────────────────────────────────────────────
    inc  = d["income"]; fix=d["fixed"]; ext=d["extras"]; subs=d["subs"]
    cc   = db.cc_total_from_data(d["cc_all"], month)
    t_inc= sum(r["amount"] for r in inc)
    t_gas= sum(r["amount"] for r in fix)+cc+sum(r["amount"] for r in ext)+sum(r["amount"] for r in subs if r["active"])
    sobra= t_inc-t_gas
    cor  = "#16a34a" if sobra>=0 else "#ef4444"
    ef   = d["ef"]
    t_inv= db.investment_last_total(d["investments"])

    st.markdown(f"""<div style="display:flex;align-items:center;justify-content:space-between;padding:4px 0 14px;border-bottom:1px solid #e5e7eb;margin-bottom:16px">
      <div style="display:flex;align-items:center;gap:10px">
        <div style="width:32px;height:32px;border-radius:50%;border:2px solid #00c896;display:flex;align-items:center;justify-content:center;font-size:14px">💚</div>
        <div><div style="font-size:14px;font-weight:700;color:#1a2332">minhas<span style="color:#00c896">Finanças</span></div><div style="font-size:10px;color:#6b7280">{ML(month)}</div></div>
      </div>
      <div style="display:flex;gap:18px">
        <div style="text-align:center"><div style="font-size:9px;text-transform:uppercase;letter-spacing:1px;color:#6b7280">Entradas</div><div style="font-size:14px;font-weight:700;color:#16a34a;font-family:DM Mono,monospace">{R(t_inc)}</div></div>
        <div style="width:1px;background:#e5e7eb"></div>
        <div style="text-align:center"><div style="font-size:9px;text-transform:uppercase;letter-spacing:1px;color:#6b7280">Gastos</div><div style="font-size:14px;font-weight:700;color:#ef4444;font-family:DM Mono,monospace">{R(t_gas)}</div></div>
        <div style="width:1px;background:#e5e7eb"></div>
        <div style="text-align:center"><div style="font-size:9px;text-transform:uppercase;letter-spacing:1px;color:#6b7280">Saldo</div><div style="font-size:14px;font-weight:700;color:{cor};font-family:DM Mono,monospace">{R(sobra)}</div></div>
        <div style="width:1px;background:#e5e7eb"></div>
        <div style="text-align:center"><div style="font-size:9px;text-transform:uppercase;letter-spacing:1px;color:#6b7280">Guardado</div><div style="font-size:14px;font-weight:700;color:#3b82f6;font-family:DM Mono,monospace">{R(t_inv+ef)}</div></div>
      </div></div>""", unsafe_allow_html=True)

    t1,t2,t3,t4,t5,t6,t7,t8,t9=st.tabs(["📊 Painel","🏠 Contas Fixas","📋 Planilha","💳 Variável","📈 Investimentos","⚠️ Dívidas","🎯 Metas","🤖 Consultor IA","⚙️ Config"])
    with t1: tab_painel(month, d)
    with t2: tab_contas(month, d)
    with t3: tab_planilha(month, d)
    with t4: tab_variavel(month, d)
    with t5: tab_investimentos(month, d)
    with t6: tab_dividas(d)
    with t7: tab_metas(d)
    with t8: tab_assistente(month, d)
    with t9: tab_config(d)


if __name__ == "__main__":
    main()
