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

# Banco de trabalho: só a carga abre (leitura e escrita).
ARQUIVO_DW = RAIZ / os.environ.get("DW_ARQUIVO", "dados/dw.duckdb")
# Banco publicado: cópia das marts, trocada de uma vez ao fim de cada carga bem-sucedida. Só a API lê.
ARQUIVO_PUBLICADO = RAIZ / os.environ.get("DW_PUBLICADO", "dados/publicado.duckdb")
# Resultado da última carga (inclusive das que falharam e não publicaram).
ARQUIVO_STATUS = RAIZ / os.environ.get("DW_STATUS", "dados/ultima_carga.json")
FUSO = os.environ.get("FUSO", "America/Fortaleza")

API_HOST = os.environ.get("API_HOST", "127.0.0.1")
API_PORTA = int(os.environ.get("API_PORTA", "8000"))
# Origens do navegador autorizadas a chamar a API (separadas por vírgula). O padrão cobre o Vite em desenvolvimento.
API_ORIGENS_CORS = [o.strip() for o in os.environ.get("API_ORIGENS_CORS", "http://localhost:5173").split(",") if o.strip()]
# Pasta do frontend já compilado (npm run build). Se existir, a API também serve o painel em "/".
PASTA_WEB = RAIZ / "web" / "dist"


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
