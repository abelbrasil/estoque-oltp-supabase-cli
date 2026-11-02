"""Publicação: copia as marts para um arquivo separado, só de leitura para a API.

Por que um arquivo separado:
  - O DuckDB permite um único processo escrevendo. Se a API lesse o banco de trabalho, a carga
    falharia sempre que a API estivesse aberta (ou a API ficaria fora do ar durante a carga).
  - A troca é atômica (os.replace): a API vê a versão anterior inteira ou a nova inteira, nunca
    uma carga pela metade.
  - Só se publica quando todos os testes passam: dado inconsistente não chega ao painel.
"""
import json
import os
import time
from pathlib import Path

from analitico.config import ARQUIVO_PUBLICADO, ARQUIVO_STATUS

ESQUEMAS_PUBLICADOS = ("marts", "meta")


def publicar(dw) -> Path:
    tmp = ARQUIVO_PUBLICADO.with_name(ARQUIVO_PUBLICADO.name + ".novo")
    tmp.unlink(missing_ok=True)
    ARQUIVO_PUBLICADO.parent.mkdir(parents=True, exist_ok=True)

    banco = dw.execute("select current_database()").fetchone()[0]
    tabelas = dw.execute(
        "select schema_name, table_name from duckdb_tables() where database_name = ? and schema_name in ? "
        "order by 1, 2", [banco, list(ESQUEMAS_PUBLICADOS)]).fetchall()

    dw.execute(f"attach '{tmp.as_posix()}' as pub")
    try:
        for esquema in ESQUEMAS_PUBLICADOS:
            dw.execute(f"create schema pub.{esquema}")
        for esquema, tabela in tabelas:
            dw.execute(f"create table pub.{esquema}.{tabela} as select * from {esquema}.{tabela}")
    finally:
        dw.execute("detach pub")

    # No Windows a troca falha se o arquivo estiver aberto naquele instante; tenta de novo.
    for tentativa in range(10):
        try:
            os.replace(tmp, ARQUIVO_PUBLICADO)
            break
        except PermissionError:
            if tentativa == 9:
                raise
            time.sleep(0.5)
    return ARQUIVO_PUBLICADO


def gravar_status(dados: dict) -> None:
    ARQUIVO_STATUS.parent.mkdir(parents=True, exist_ok=True)
    tmp = ARQUIVO_STATUS.with_name(ARQUIVO_STATUS.name + ".novo")
    tmp.write_text(json.dumps(dados, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    os.replace(tmp, ARQUIVO_STATUS)


def ler_status() -> dict | None:
    try:
        return json.loads(ARQUIVO_STATUS.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None
