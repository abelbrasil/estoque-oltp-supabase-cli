"""Acesso ao banco publicado: uma conexão só de leitura por requisição."""
import time
from datetime import date, timedelta
from dataclasses import dataclass

import duckdb
from fastapi import Depends, Query

from analitico.api.erros import ErroApi
from analitico.config import ARQUIVO_PUBLICADO

MAX_DIAS_PERIODO = 366


def conexao():
    if not ARQUIVO_PUBLICADO.exists():
        raise ErroApi(503, "SEM_DADOS_PUBLICADOS",
                      "Nenhuma carga foi publicada ainda. Rode `poetry run carga`.", headers={"Retry-After": "30"})
    for tentativa in range(5):
        try:
            con = duckdb.connect(str(ARQUIVO_PUBLICADO), read_only=True)
            break
        except duckdb.IOException:
            if tentativa == 4:
                raise ErroApi(503, "BANCO_INDISPONIVEL", "Banco publicado indisponível no momento. Tente de novo.",
                              headers={"Retry-After": "5"})
            time.sleep(0.2)
    try:
        yield con
    finally:
        con.close()


def linhas(con, sql: str, params=None) -> list[dict]:
    cur = con.execute(sql, params or [])
    nomes = [d[0] for d in cur.description]
    return [dict(zip(nomes, r)) for r in cur.fetchall()]


def valor(con, sql: str, params=None):
    return con.execute(sql, params or []).fetchone()[0]


@dataclass
class Filtros:
    inicio: date
    fim: date
    almoxarifados: list[str]
    materiais: list[str]

    @property
    def dias(self) -> int:
        return (self.fim - self.inicio).days + 1


def filtros(
    inicio: date | None = Query(None, description="Primeiro dia (AAAA-MM-DD). Padrão: 29 dias antes do fim."),
    fim: date | None = Query(None, description="Último dia (AAAA-MM-DD). Padrão: último dia com dados."),
    almoxarifado: list[str] | None = Query(None, description="Repita para vários. Ex.: estoque:CENTRAL. Padrão: todos."),
    material: list[str] | None = Query(None, description="Repita para vários. Ex.: estoque:1. Padrão: todos."),
    con=Depends(conexao),
) -> Filtros:
    d_min, d_max = con.execute("select min(dia), max(dia) from marts.dim_tempo").fetchone()
    fim = fim or d_max
    inicio = inicio or max(d_min, fim - timedelta(days=29))
    problemas = []
    if inicio > fim:
        problemas.append({"parametro": "inicio", "problema": "inicio deve ser menor ou igual a fim"})
    if (fim - inicio).days + 1 > MAX_DIAS_PERIODO:
        problemas.append({"parametro": "fim", "problema": f"período máximo de {MAX_DIAS_PERIODO} dias"})
    if inicio < d_min or fim > d_max:
        problemas.append({"parametro": "inicio/fim",
                          "problema": f"dados disponíveis de {d_min:%Y-%m-%d} a {d_max:%Y-%m-%d}"})

    todos_alm = [r[0] for r in con.execute("select almoxarifado_id from marts.dim_almoxarifado").fetchall()]
    todos_mat = [r[0] for r in con.execute("select material_id from marts.dim_material").fetchall()]
    for nome, pedidos, validos in (("almoxarifado", almoxarifado, todos_alm), ("material", material, todos_mat)):
        invalidos = sorted(set(pedidos or []) - set(validos))
        if invalidos:
            problemas.append({"parametro": nome, "problema": f"inexistente: {', '.join(invalidos)}"})
    if problemas:
        raise ErroApi(422, "PARAMETRO_INVALIDO", "Filtro inválido.", problemas)

    return Filtros(inicio, fim, sorted(set(almoxarifado)) if almoxarifado else todos_alm,
                   sorted(set(material)) if material else todos_mat)
