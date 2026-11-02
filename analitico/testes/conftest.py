"""Banco analítico de teste, montado com dados pequenos e conhecidos (não precisa de Postgres).

As variáveis de ambiente são definidas ANTES de importar o pacote, para que tudo aponte para a pasta temporária.
"""
import os
import tempfile
from datetime import date, datetime
from pathlib import Path

PASTA = Path(tempfile.mkdtemp(prefix="analitico-testes-"))
os.environ["DW_ARQUIVO"] = str(PASTA / "dw.duckdb")
os.environ["DW_PUBLICADO"] = str(PASTA / "publicado.duckdb")
os.environ["DW_STATUS"] = str(PASTA / "ultima_carga.json")
os.environ["FUSO"] = "America/Fortaleza"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from analitico.carga import DDL_META, testar, transformar  # noqa: E402
from analitico.config import conectar_dw  # noqa: E402
from analitico.origens.estoque_supabase import DDL_RAW  # noqa: E402
from analitico.publicacao import gravar_status, publicar  # noqa: E402

# Material 1: Luva (CX, R$ 10,00). Material 2: Agulha (UN, R$ 0,50).
MATERIAIS = [(1, "Luva", "CX", 10.0), (2, "Agulha", "UN", 0.5)]
# seq, transacao, usuario, material, almox, tipo, quantidade, valor, data/hora local
MOVIMENTOS = [
    (1, 1, 3, 1, "CENTRAL", "NR", 100, 10.0, datetime(2026, 1, 1, 9)),
    (2, 1, 3, 2, "CENTRAL", "NR", 50, 0.5, datetime(2026, 1, 1, 9)),
    (3, 2, 1, 1, "CENTRAL", "TRS", 40, 10.0, datetime(2026, 1, 2, 10)),
    (4, 2, 1, 1, "SATELITE", "TRE", 40, 10.0, datetime(2026, 1, 2, 10)),
    (5, 2, 1, 1, "SATELITE", "RM", 10, 10.0, datetime(2026, 1, 2, 10)),
    (6, 3, 2, 1, "SATELITE", "RM", 30, 10.0, datetime(2026, 1, 3, 15)),
    (7, 4, 2, 1, "CENTRAL", "TRS", 20, 10.0, datetime(2026, 1, 4, 12)),
    (8, 4, 2, 1, "SATELITE", "TRE", 20, 10.0, datetime(2026, 1, 4, 12)),
    (9, 4, 2, 1, "SATELITE", "RM", 5, 10.0, datetime(2026, 1, 4, 12)),
]
# Saldo como a origem mantém (Agulha nunca foi ao satélite: sem linha)
SALDO_ORIGEM = [(1, "CENTRAL", 40), (1, "SATELITE", 15), (2, "CENTRAL", 50)]


def montar_banco(saldo_origem=SALDO_ORIGEM):
    dw = conectar_dw()
    dw.execute(DDL_RAW)
    dw.execute(DDL_META)
    dw.execute("delete from raw.estoque__materiais; delete from raw.estoque__movimentos; delete from raw.estoque__saldo")
    dw.executemany("insert into raw.estoque__materiais values (?, ?, ?, ?)", MATERIAIS)
    dw.executemany("insert into raw.estoque__movimentos values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                   [(*m[:8], m[8], m[8], m[8].date()) for m in MOVIMENTOS])
    dw.executemany("insert into raw.estoque__saldo values (?, ?, ?, now())", saldo_origem)
    dw.execute("create or replace table meta.parametros as select ?::date as data_referencia", [date(2026, 1, 4)])
    transformar(dw)
    return dw


@pytest.fixture(scope="session")
def cliente():
    dw = montar_banco()
    assert testar(dw) == []
    dw.execute("insert into meta.cargas (inicio, fim, data_referencia, status, testes_com_falha, mensagem) "
               "values (now(), now(), '2026-01-04', 'OK', 0, '')")
    publicar(dw)
    dw.close()
    gravar_status({"id": 1, "status": "OK", "fim": datetime.now(), "publicado": True, "mensagem": ""})

    from analitico.api.app import app
    with TestClient(app) as c:
        yield c
