"""Dashboard diário de estoque. Lê somente as tabelas marts do banco analítico."""
from datetime import timedelta

import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st

from analitico.config import ARQUIVO_DW, conectar_dw

st.set_page_config(page_title="Painel de Estoque", page_icon="📦", layout="wide")

st.markdown("""
<style>
.block-container {padding-top: 2rem;}
.card {border: 1px solid rgba(128,128,128,.25); border-radius: 12px; padding: 14px 18px;
       background: rgba(128,128,128,.06); height: 100%;}
.card .rotulo {font-size: .85rem; opacity: .75;}
.card .valor {font-size: 1.75rem; font-weight: 700; margin: .15rem 0;}
.card .detalhe {font-size: .8rem; opacity: .7;}
.card .sobe {color: #1a9c5b;} .card .desce {color: #d64545;}
</style>
""", unsafe_allow_html=True)


# ---------- formatação pt-BR ----------
def br(v, casas=0):
    if v is None or pd.isna(v):
        return "–"
    return f"{v:,.{casas}f}".replace(",", "§").replace(".", ",").replace("§", ".")


def reais(v):
    return "R$ " + br(v, 2)


def duracao(horas):
    if horas is None or pd.isna(horas):
        return "–"
    return f"{br(horas / 24, 1)} dias" if horas >= 48 else f"{br(horas, 1)} h"


def card(col, rotulo, valor, detalhe=""):
    col.markdown(f'<div class="card"><div class="rotulo">{rotulo}</div>'
                 f'<div class="valor">{valor}</div><div class="detalhe">{detalhe}</div></div>',
                 unsafe_allow_html=True)


def grafico(fig, eixo_y):
    fig.update_layout(separators=",.", margin=dict(l=10, r=10, t=10, b=10), height=380,
                      legend=dict(orientation="h", y=-0.18, title=None), xaxis_title=None, yaxis_title=eixo_y,
                      hovermode="x unified")
    fig.update_xaxes(tickformat="%d/%m", hoverformat="%d/%m/%Y")
    st.plotly_chart(fig, width="stretch")


# ---------- acesso ao banco analítico ----------
@st.cache_data(ttl=60, show_spinner=False)
def consultar(sql, params=None):
    con = conectar_dw(somente_leitura=True)
    try:
        return con.execute(sql, params or []).df()
    finally:
        con.close()


if not ARQUIVO_DW.exists():
    st.error(f"Banco analítico não encontrado em {ARQUIVO_DW}. Rode `poetry run carga` primeiro.")
    st.stop()
try:
    cargas = consultar("select fim, status, mensagem from meta.cargas order by id desc limit 1")
    materiais = consultar("select material_id, nome, unidade from marts.dim_material order by nome")
    almoxes = consultar("select almoxarifado_id, nome from marts.dim_almoxarifado order by nome")
    limites = consultar("select min(dia) as ini, max(dia) as fim from marts.dim_tempo")
except duckdb.IOException:
    st.warning("Uma carga está gravando no banco analítico agora. Atualize a página em alguns segundos.")
    st.stop()
except duckdb.CatalogException:
    st.error("O banco analítico ainda não tem as tabelas do painel. Rode `poetry run carga`.")
    st.stop()

ini, fim = limites.ini[0].date(), limites.fim[0].date()

# ---------- cabeçalho e filtros ----------
st.title("Dashboard Diário de Estoque")
ult = cargas.iloc[0] if len(cargas) else None
if ult is not None:
    situacao = "✅ dados conferidos com a origem" if ult.status == "OK" else f"⚠️ {ult.status}: {ult.mensagem}"
    st.caption(f"Origem: estoque (Supabase) · Última carga: {ult.fim:%d/%m/%Y %H:%M} · {situacao}")

f1, f2, f3 = st.columns([2, 2, 4])
periodo = f1.date_input("Período", value=(max(ini, fim - timedelta(days=29)), fim),
                        min_value=ini, max_value=fim, format="DD/MM/YYYY")
if not isinstance(periodo, tuple) or len(periodo) != 2:
    st.info("Escolha a data final do período.")
    st.stop()
d_ini, d_fim = periodo
dias_periodo = (d_fim - d_ini).days + 1

nomes_alm = f2.multiselect("Almoxarifado", almoxes.nome.tolist(), default=almoxes.nome.tolist())
nomes_mat = f3.multiselect("Materiais", materiais.nome.tolist(), placeholder="Todos os materiais")
alm_ids = almoxes[almoxes.nome.isin(nomes_alm)].almoxarifado_id.tolist()
mat_ids = materiais[materiais.nome.isin(nomes_mat)].material_id.tolist() if nomes_mat else materiais.material_id.tolist()
# Cada material mantém a mesma cor em todos os gráficos
paleta = px.colors.qualitative.Safe + px.colors.qualitative.Pastel
cores = dict(color_discrete_map={n: paleta[i % len(paleta)] for i, n in enumerate(materiais.nome)},
             category_orders={"material": materiais.nome.tolist()})

if not alm_ids:
    st.info("Selecione ao menos um almoxarifado.")
    st.stop()

# ---------- dados filtrados ----------
saldo_atual = consultar(
    "select * from marts.mart_saldo_atual where list_contains(?, almoxarifado_id) and list_contains(?, material_id)",
    [alm_ids, mat_ids])
diario = consultar(
    """select s.dia, m.nome as material, sum(s.saldo_fim_dia) as saldo, sum(s.consumo) as consumo,
              sum(s.entradas) as entradas, sum(s.valor_fim_dia) as valor
         from marts.fato_saldo_diario s join marts.dim_material m using (material_id)
        where s.dia between ? and ? and list_contains(?, s.almoxarifado_id) and list_contains(?, s.material_id)
        group by 1, 2 order by 1, 2""",
    [d_ini, d_fim, alm_ids, mat_ids])
valor_inicio = consultar(
    """select coalesce(sum(valor_fim_dia), 0) as v from marts.fato_saldo_diario
        where dia = ? and list_contains(?, almoxarifado_id) and list_contains(?, material_id)""",
    [d_ini - timedelta(days=1), alm_ids, mat_ids]).v[0]
reposicoes = consultar(
    """select r.dia, r.data_hora, m.nome as material, r.quantidade, r.horas_desde_anterior
         from marts.fato_reposicao_satelite r join marts.dim_material m using (material_id)
        where r.dia between ? and ? and list_contains(?, r.material_id)""",
    [d_ini, d_fim, mat_ids])

# ---------- indicadores ----------
c1, c2, c3, c4 = st.columns(4)
valor_total = saldo_atual.valor.sum()
partes = " · ".join(f"{a}: {reais(v)}" for a, v in saldo_atual.groupby("almoxarifado").valor.sum().items())
variacao = ""
if valor_inicio:
    pct = (valor_total / valor_inicio - 1) * 100
    variacao = f'<span class="{"sobe" if pct >= 0 else "desce"}">{"▲" if pct >= 0 else "▼"} {br(abs(pct), 1)}%</span> desde o início do período<br>'
card(c1, "Valor financeiro em estoque (atual)", reais(valor_total), variacao + partes)

zeradas = int((saldo_atual.saldo == 0).sum())
card(c2, "Posições com saldo zerado (atual)", br(zeradas),
     f"de {br(len(saldo_atual))} posições (material × almoxarifado)")

n_rep = len(reposicoes)
card(c3, "Reposições do satélite no período", br(n_rep),
     f"média de {br(n_rep / dias_periodo, 1)} por dia em {br(dias_periodo)} dias")

card(c4, "Intervalo médio entre reposições", duracao(reposicoes.horas_desde_anterior.mean()),
     "tempo entre duas reposições do mesmo material")

st.write("")

# ---------- saldo atual ----------
st.subheader("Saldo atual por material")
tabela = saldo_atual.pivot_table(index=["material", "unidade", "valor_unitario"], columns="almoxarifado",
                                 values="saldo", aggfunc="sum", fill_value=0).reset_index()
tabela.columns.name = None
cols_alm = [a for a in ("Central", "Satélite") if a in tabela.columns]
tabela["Total"] = tabela[cols_alm].sum(axis=1)
tabela["Valor em estoque"] = tabela["Total"] * tabela["valor_unitario"]
tabela = tabela.rename(columns={"material": "Material", "unidade": "Unidade", "valor_unitario": "Valor unitário"})
tabela = tabela[["Material", "Unidade", *cols_alm, "Total", "Valor unitário", "Valor em estoque"]]
tabela = tabela.sort_values("Valor em estoque", ascending=False)
st.dataframe(
    tabela.style.format({**{c: br for c in [*cols_alm, "Total"]}, "Valor unitário": reais, "Valor em estoque": reais})
         .map(lambda v: "color: #d64545; font-weight: 600" if v == 0 else "", subset=[*cols_alm, "Total"]),
    hide_index=True, width="stretch")

# ---------- quantidade por dia ----------
st.subheader("Quantidade por dia")
medidas = {"Saldo no fim do dia": ("saldo", "Quantidade"),
           "Consumo (requisições RM)": ("consumo", "Quantidade"),
           "Entradas (compras NR e transferências TRE)": ("entradas", "Quantidade"),
           "Valor em estoque (R$)": ("valor", "R$")}
escolha = st.radio("Medida", list(medidas), horizontal=True, label_visibility="collapsed")
coluna, eixo = medidas[escolha]
st.caption("Cada material tem sua própria unidade (CX, UN, FR...): compare as linhas pela tendência, não pelo total.")
grafico(px.line(diario, x="dia", y=coluna, color="material", markers=len(diario.dia.unique()) <= 31, **cores), eixo)

# ---------- frequência de reposição ----------
st.subheader("Frequência de reposição do satélite")
por_dia = reposicoes.groupby(["dia", "material"]).size().reset_index(name="reposicoes")
if por_dia.empty:
    st.info("Nenhuma reposição no período.")
else:
    fig = px.bar(por_dia, x="dia", y="reposicoes", color="material", **cores)
    fig.update_yaxes(tickformat=",d")
    grafico(fig, "Reposições")
if not reposicoes.empty:
    resumo = (reposicoes.groupby("material")
              .agg(reposicoes=("quantidade", "size"), qtd_media=("quantidade", "mean"),
                   intervalo=("horas_desde_anterior", "mean"), ultima=("data_hora", "max"))
              .reset_index().sort_values("reposicoes", ascending=False))
    resumo["por_dia"] = resumo.reposicoes / dias_periodo
    resumo = resumo[["material", "reposicoes", "por_dia", "intervalo", "qtd_media", "ultima"]].rename(columns={
        "material": "Material", "reposicoes": "Reposições", "por_dia": "Por dia", "intervalo": "Intervalo médio",
        "qtd_media": "Qtde média reposta", "ultima": "Última"})
    st.dataframe(resumo.style.format({"Reposições": br, "Por dia": lambda v: br(v, 2), "Intervalo médio": duracao,
                                      "Qtde média reposta": br, "Última": lambda v: f"{v:%d/%m %H:%M}"}),
                 hide_index=True, width="stretch")
