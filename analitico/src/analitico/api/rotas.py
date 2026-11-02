"""Rotas /api/v1. Todas leem só as marts do banco publicado e aceitam os mesmos filtros."""
from datetime import timedelta

import duckdb
from fastapi import APIRouter, Depends, Query

from analitico.api import esquemas as E
from analitico.api.banco import Filtros, conexao, filtros, linhas, valor
from analitico.config import ARQUIVO_PUBLICADO
from analitico.publicacao import ler_status

rotas = APIRouter(prefix="/api/v1")


def _periodo(f: Filtros) -> E.Periodo:
    return E.Periodo(inicio=f.inicio, fim=f.fim, dias=f.dias)


@rotas.get("/saude", response_model=E.Saude, tags=["Sistema"],
           summary="Situação da API, da carga publicada e da última carga")
def saude():
    ultima = ler_status()
    publicada = None
    if ARQUIVO_PUBLICADO.exists():
        try:
            con = duckdb.connect(str(ARQUIVO_PUBLICADO), read_only=True)
            try:
                r = linhas(con, "select id, status, fim, data_referencia, mensagem from meta.cargas "
                                "where status = 'OK' order by id desc limit 1")
                publicada = r[0] if r else None
            finally:
                con.close()
        except duckdb.Error:
            publicada = None
    alerta = None
    if ultima and ultima.get("status") != "OK":
        quando = f" (dados da carga de {publicada['fim']:%d/%m/%Y %H:%M})" if publicada else ""
        alerta = f"A última carga terminou com {ultima['status']} e não foi publicada{quando}: {ultima.get('mensagem')}"
    return E.Saude(api="ok", dados_publicados=publicada is not None, carga_publicada=publicada,
                   ultima_carga=ultima, alerta=alerta)


@rotas.get("/filtros", response_model=E.Filtros, tags=["Painel"],
           summary="Opções para os filtros: período disponível, almoxarifados e materiais")
def opcoes_filtros(con=Depends(conexao), f: Filtros = Depends(filtros)):
    d_min, d_max = con.execute("select min(dia), max(dia) from marts.dim_tempo").fetchone()
    return E.Filtros(
        periodo_disponivel=E.Periodo(inicio=d_min, fim=d_max, dias=(d_max - d_min).days + 1),
        periodo_padrao=_periodo(f),
        almoxarifados=linhas(con, "select almoxarifado_id as id, nome from marts.dim_almoxarifado order by nome"),
        materiais=linhas(con, "select material_id as id, nome, unidade, valor_unitario "
                              "from marts.dim_material order by nome"),
    )


@rotas.get("/indicadores", response_model=E.Indicadores, tags=["Painel"],
           summary="Cards: valor em estoque, posições zeradas e reposições do satélite")
def indicadores(con=Depends(conexao), f: Filtros = Depends(filtros)):
    por_alm = linhas(con, """
        select almoxarifado_id, almoxarifado, sum(valor) as valor,
               count(*) filter (where saldo = 0) as zeradas, count(*) as total
          from marts.mart_saldo_atual
         where list_contains(?, almoxarifado_id) and list_contains(?, material_id)
         group by 1, 2 order by 2""", [f.almoxarifados, f.materiais])
    atual = float(sum(r["valor"] for r in por_alm))
    inicio = float(valor(con, """
        select coalesce(sum(valor_fim_dia), 0) from marts.fato_saldo_diario
         where dia = ? and list_contains(?, almoxarifado_id) and list_contains(?, material_id)""",
                         [f.inicio - timedelta(days=1), f.almoxarifados, f.materiais]))
    total_rep, intervalo = con.execute("""
        select count(*), avg(horas_desde_anterior) from marts.fato_reposicao_satelite
         where dia between ? and ? and list_contains(?, material_id)""",
                                       [f.inicio, f.fim, f.materiais]).fetchone()
    return E.Indicadores(
        periodo=_periodo(f),
        valor_estoque=E.ValorEstoque(
            atual=round(atual, 2), inicio_periodo=round(inicio, 2),
            variacao_pct=round((atual / inicio - 1) * 100, 2) if inicio else None,
            por_almoxarifado=[{**r, "valor": round(float(r["valor"]), 2)} for r in por_alm]),
        posicoes_zeradas=E.PosicoesZeradas(zeradas=sum(r["zeradas"] for r in por_alm),
                                           total=sum(r["total"] for r in por_alm)),
        reposicoes_satelite=E.ReposicoesResumo(
            total=total_rep, media_por_dia=round(total_rep / f.dias, 3),
            intervalo_medio_horas=round(float(intervalo), 2) if intervalo is not None else None),
    )


@rotas.get("/saldo-atual", response_model=list[E.SaldoMaterial], tags=["Painel"],
           summary="Saldo e valor atuais por material, separados por almoxarifado")
def saldo_atual(con=Depends(conexao), f: Filtros = Depends(filtros)):
    dados = linhas(con, """
        select material_id, material, unidade, valor_unitario, almoxarifado_id, almoxarifado, saldo, valor
          from marts.mart_saldo_atual
         where list_contains(?, almoxarifado_id) and list_contains(?, material_id)
         order by material, almoxarifado""", [f.almoxarifados, f.materiais])
    por_mat: dict[str, dict] = {}
    for r in dados:
        m = por_mat.setdefault(r["material_id"], {
            "material_id": r["material_id"], "material": r["material"], "unidade": r["unidade"],
            "valor_unitario": r["valor_unitario"], "por_almoxarifado": [], "total": 0, "valor": 0})
        m["por_almoxarifado"].append({k: r[k] for k in ("almoxarifado_id", "almoxarifado", "saldo")})
        m["total"] += r["saldo"]
        m["valor"] += r["valor"]
    return sorted(por_mat.values(), key=lambda m: m["valor"], reverse=True)


COLUNA_MEDIDA = {E.Medida.saldo: "saldo_fim_dia", E.Medida.consumo: "consumo",
                 E.Medida.entradas: "entradas", E.Medida.valor: "valor_fim_dia"}


@rotas.get("/series/quantidade-diaria", response_model=E.SerieDiaria, tags=["Painel"],
           summary="Uma série por material, um ponto por dia (somando os almoxarifados filtrados)")
def quantidade_diaria(medida: E.Medida = Query(E.Medida.saldo, description="saldo, consumo, entradas ou valor"),
                      con=Depends(conexao), f: Filtros = Depends(filtros)):
    dados = linhas(con, f"""
        select s.material_id, m.nome as material, m.unidade, s.dia, sum(s.{COLUNA_MEDIDA[medida]}) as valor
          from marts.fato_saldo_diario s join marts.dim_material m using (material_id)
         where s.dia between ? and ? and list_contains(?, s.almoxarifado_id) and list_contains(?, s.material_id)
         group by 1, 2, 3, 4 order by 2, 4""", [f.inicio, f.fim, f.almoxarifados, f.materiais])
    series: dict[str, dict] = {}
    for r in dados:
        s = series.setdefault(r["material_id"], {k: r[k] for k in ("material_id", "material", "unidade")} | {"pontos": []})
        s["pontos"].append({"dia": r["dia"], "valor": round(float(r["valor"]), 3)})
    return E.SerieDiaria(medida=medida, periodo=_periodo(f), series=list(series.values()))


@rotas.get("/reposicoes/diarias", response_model=E.ReposicoesDiarias, tags=["Painel"],
           summary="Reposições do satélite por dia e material (só dias com reposição)")
def reposicoes_diarias(con=Depends(conexao), f: Filtros = Depends(filtros)):
    itens = linhas(con, """
        select r.dia, r.material_id, m.nome as material, count(*) as reposicoes
          from marts.fato_reposicao_satelite r join marts.dim_material m using (material_id)
         where r.dia between ? and ? and list_contains(?, r.material_id)
         group by 1, 2, 3 order by 1, 3""", [f.inicio, f.fim, f.materiais])
    return E.ReposicoesDiarias(periodo=_periodo(f), itens=itens)


@rotas.get("/reposicoes/por-material", response_model=E.ReposicoesPorMaterial, tags=["Painel"],
           summary="Frequência de reposição do satélite por material")
def reposicoes_por_material(con=Depends(conexao), f: Filtros = Depends(filtros)):
    itens = linhas(con, """
        select r.material_id, m.nome as material, count(*) as reposicoes,
               round(count(*) / ?, 3) as por_dia,
               round(avg(r.horas_desde_anterior), 2) as intervalo_medio_horas,
               round(avg(r.quantidade), 1) as quantidade_media, max(r.data_hora) as ultima
          from marts.fato_reposicao_satelite r join marts.dim_material m using (material_id)
         where r.dia between ? and ? and list_contains(?, r.material_id)
         group by 1, 2 order by reposicoes desc, material""", [f.dias, f.inicio, f.fim, f.materiais])
    return E.ReposicoesPorMaterial(periodo=_periodo(f), itens=itens)
