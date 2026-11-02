"""Origem 1: banco OLTP de estoque (Supabase / Postgres, schema estoque).

Como a carga garante que nada se perde (a "verificação"):
  - Toda a leitura da origem acontece em UMA transação REPEATABLE READ: o ledger, o saldo e o
    cadastro são lidos no mesmo instante lógico, mesmo com os geradores A e B rodando.
  - O ledger não é lido "a partir do último seq" (um seq menor pode ser confirmado depois de um
    maior e seria pulado). Em vez disso, a carga compara, DIA A DIA, uma impressão digital da
    origem com a do banco analítico: quantidade de linhas, soma dos seq e soma das quantidades.
    Todo dia que difere (ou que só existe de um dos lados) é apagado e recarregado inteiro.
  - Como o ledger é imutável, na prática só o dia de hoje é recarregado; um commit atrasado ou um
    reset da origem (99_reset_movimentos) também são detectados e corrigidos.
Cadastro de materiais e saldo atual são pequenos e são copiados por inteiro a cada carga.
"""
from dataclasses import dataclass
from datetime import date

import pandas as pd
import psycopg2

from analitico.config import FUSO, variavel

ORIGEM = "estoque"

DDL_RAW = """
create schema if not exists raw;
create table if not exists raw.estoque__materiais (
    codigo integer primary key, nome varchar, unidade_medida varchar, valor_unitario decimal(14,4)
);
create table if not exists raw.estoque__saldo (
    mat_codigo integer, almoxarifado varchar, qtde_disponivel decimal(14,3), dt_atualizacao timestamptz,
    primary key (mat_codigo, almoxarifado)
);
create table if not exists raw.estoque__movimentos (
    seq bigint primary key, transacao_id bigint, usr_codigo smallint, mat_codigo integer,
    almoxarifado varchar, tipo_movimento varchar, quantidade decimal(14,3), valor_unitario decimal(14,4),
    dt_geracao timestamptz, dt_local timestamp, dia_local date
);
"""

SQL_DIGITAL_ORIGEM = """
select (dt_geracao at time zone %(fuso)s)::date as dia, count(*), sum(seq), sum(quantidade)
  from estoque.sce_movimento_materiais
 group by 1
"""

SQL_DIGITAL_DW = """
select dia_local, count(*), sum(seq), sum(quantidade)
  from raw.estoque__movimentos
 group by 1
"""

SQL_MOVIMENTOS_DOS_DIAS = """
select seq, transacao_id, usr_codigo, mat_codigo, almoxarifado, tipo_movimento, quantidade,
       valor_unitario, dt_geracao,
       dt_geracao at time zone %(fuso)s as dt_local,
       (dt_geracao at time zone %(fuso)s)::date as dia_local
  from estoque.sce_movimento_materiais
 where (dt_geracao at time zone %(fuso)s)::date = any(%(dias)s::date[])
"""


@dataclass
class Resultado:
    dias_verificados: int
    dias_recarregados: list[date]
    linhas_movimento: int
    linhas_saldo: int
    linhas_materiais: int


def _consulta(cur, sql, params=None) -> pd.DataFrame:
    cur.execute(sql, params)
    return pd.DataFrame(cur.fetchall(), columns=[d[0] for d in cur.description])


def _digital(linhas) -> dict:
    return {dia: (int(n), int(soma_seq), soma_qtd) for dia, n, soma_seq, soma_qtd in linhas}


def extrair(dw, recarregar_tudo: bool = False) -> Resultado:
    dw.execute(DDL_RAW)
    if recarregar_tudo:
        dw.execute("delete from raw.estoque__movimentos")

    conn = psycopg2.connect(variavel("ESTOQUE_DB_URL"))
    conn.set_session(isolation_level="REPEATABLE READ", readonly=True)
    try:
        cur = conn.cursor()

        # 1) Impressão digital por dia, dos dois lados, e os dias que precisam ser recarregados
        cur.execute(SQL_DIGITAL_ORIGEM, {"fuso": FUSO})
        origem = _digital(cur.fetchall())
        destino = _digital(dw.execute(SQL_DIGITAL_DW).fetchall())
        dias = sorted(d for d in origem.keys() | destino.keys() if origem.get(d) != destino.get(d))

        # 2) Movimentos dos dias divergentes (lidos no mesmo snapshot da digital)
        movimentos = _consulta(cur, SQL_MOVIMENTOS_DOS_DIAS, {"fuso": FUSO, "dias": dias}) if dias else None

        # 3) Cadastro e saldo atual (cópia integral, mesmo snapshot)
        materiais = _consulta(cur, "select codigo, nome, unidade_medida, valor_unitario from estoque.sco_materiais")
        saldo = _consulta(cur, "select mat_codigo, almoxarifado, qtde_disponivel, dt_atualizacao "
                               "from estoque.sce_estq_almoxs")
        conn.commit()
    finally:
        conn.close()

    # 4) Grava tudo no DuckDB em uma transação: ou entra a carga inteira, ou nada
    dw.execute("begin")
    try:
        if dias:
            dw.register("df_dias", pd.DataFrame({"dia": dias}))
            dw.execute("delete from raw.estoque__movimentos where dia_local in (select dia from df_dias)")
            if len(movimentos):
                dw.register("df_mov", movimentos)
                dw.execute("insert into raw.estoque__movimentos select * from df_mov")
        dw.register("df_mat", materiais)
        dw.execute("delete from raw.estoque__materiais; insert into raw.estoque__materiais select * from df_mat")
        dw.register("df_saldo", saldo)
        dw.execute("delete from raw.estoque__saldo; insert into raw.estoque__saldo select * from df_saldo")
        dw.execute("commit")
    except Exception:
        dw.execute("rollback")
        raise

    return Resultado(
        dias_verificados=len(origem.keys() | destino.keys()),
        dias_recarregados=dias,
        linhas_movimento=0 if movimentos is None else len(movimentos),
        linhas_saldo=len(saldo),
        linhas_materiais=len(materiais),
    )
