"""Configuração compartilhada: caminhos, fuso e conexão com o banco analítico (DuckDB)."""
import os
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import duckdb
from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parents[2]
PASTA_SQL = RAIZ / "sql"

load_dotenv(RAIZ / "config.env")

ARQUIVO_DW = RAIZ / os.environ.get("DW_ARQUIVO", "dados/dw.duckdb")
FUSO = os.environ.get("FUSO", "America/Fortaleza")


def hoje() -> date:
    """Data de referência da carga: o dia de hoje no fuso configurado."""
    return datetime.now(ZoneInfo(FUSO)).date()


def variavel(nome: str) -> str:
    valor = os.environ.get(nome)
    if not valor:
        raise SystemExit(f"{nome} não definida em config.env")
    return valor


def conectar_dw(somente_leitura: bool = False) -> duckdb.DuckDBPyConnection:
    """Abre o DuckDB. Só um processo pode escrever por vez; leitores usam somente_leitura=True."""
    ARQUIVO_DW.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(ARQUIVO_DW), read_only=somente_leitura)
