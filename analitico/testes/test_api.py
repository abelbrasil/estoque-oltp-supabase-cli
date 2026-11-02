"""Rotas da API conferidas contra valores calculados à mão a partir dos dados do conftest."""
import pytest

PERIODO = {"inicio": "2026-01-02", "fim": "2026-01-04"}


def test_saude(cliente):
    r = cliente.get("/api/v1/saude").json()
    assert r["api"] == "ok" and r["dados_publicados"] is True and r["alerta"] is None


def test_filtros_e_periodo_padrao(cliente):
    r = cliente.get("/api/v1/filtros").json()
    assert r["periodo_disponivel"] == {"inicio": "2026-01-01", "fim": "2026-01-04", "dias": 4}
    assert r["periodo_padrao"]["inicio"] == "2026-01-01"  # 30 dias antes cai fora: limita ao primeiro dia
    assert [m["nome"] for m in r["materiais"]] == ["Agulha", "Luva"]
    assert {a["id"] for a in r["almoxarifados"]} == {"estoque:CENTRAL", "estoque:SATELITE"}


def test_indicadores(cliente):
    r = cliente.get("/api/v1/indicadores", params=PERIODO).json()
    v = r["valor_estoque"]
    assert v["atual"] == 575.0               # 40*10 + 15*10 + 50*0,5
    assert v["inicio_periodo"] == 1025.0     # fim de 01/01: 100*10 + 50*0,5
    assert v["variacao_pct"] == pytest.approx(-43.90, abs=0.01)
    assert r["posicoes_zeradas"] == {"zeradas": 1, "total": 4}  # Agulha no satélite
    rep = r["reposicoes_satelite"]
    assert rep["total"] == 2 and rep["media_por_dia"] == pytest.approx(0.667, abs=0.001)
    assert rep["intervalo_medio_horas"] == 50.0  # 02/01 10h -> 04/01 12h


def test_indicadores_filtrados(cliente):
    r = cliente.get("/api/v1/indicadores", params={**PERIODO, "almoxarifado": "estoque:SATELITE",
                                                   "material": "estoque:1"}).json()
    assert r["valor_estoque"]["atual"] == 150.0
    assert r["posicoes_zeradas"] == {"zeradas": 0, "total": 1}


def test_saldo_atual(cliente):
    r = cliente.get("/api/v1/saldo-atual").json()
    assert [m["material"] for m in r] == ["Luva", "Agulha"]  # ordenado pelo valor
    luva = r[0]
    assert luva["total"] == 55 and luva["valor"] == 550.0
    assert {p["almoxarifado_id"]: p["saldo"] for p in luva["por_almoxarifado"]} == {
        "estoque:CENTRAL": 40, "estoque:SATELITE": 15}


def test_serie_consumo(cliente):
    r = cliente.get("/api/v1/series/quantidade-diaria",
                    params={**PERIODO, "medida": "consumo", "material": "estoque:1"}).json()
    assert [(p["dia"], p["valor"]) for p in r["series"][0]["pontos"]] == [
        ("2026-01-02", 10), ("2026-01-03", 30), ("2026-01-04", 5)]


def test_serie_saldo_inclui_dias_sem_movimento(cliente):
    r = cliente.get("/api/v1/series/quantidade-diaria",
                    params={"medida": "saldo", "material": "estoque:2"}).json()
    assert [p["valor"] for p in r["series"][0]["pontos"]] == [50, 50, 50, 50]


def test_reposicoes(cliente):
    dia = cliente.get("/api/v1/reposicoes/diarias", params=PERIODO).json()["itens"]
    assert [(i["dia"], i["reposicoes"]) for i in dia] == [("2026-01-02", 1), ("2026-01-04", 1)]
    mat = cliente.get("/api/v1/reposicoes/por-material", params=PERIODO).json()["itens"]
    assert mat[0]["reposicoes"] == 2 and mat[0]["quantidade_media"] == 30.0


@pytest.mark.parametrize("params, parametro", [
    ({"inicio": "2026-01-04", "fim": "2026-01-02"}, "inicio"),
    ({"material": "estoque:999"}, "material"),
    ({"almoxarifado": "X"}, "almoxarifado"),
    ({"inicio": "2025-12-01"}, "inicio/fim"),
    ({"inicio": "ontem"}, "inicio"),
])
def test_filtro_invalido_responde_422_no_formato_padrao(cliente, params, parametro):
    r = cliente.get("/api/v1/indicadores", params=params)
    assert r.status_code == 422
    erro = r.json()["erro"]
    assert erro["codigo"] == "PARAMETRO_INVALIDO"
    assert any(d["parametro"] == parametro for d in erro["detalhes"])


def test_medida_invalida(cliente):
    r = cliente.get("/api/v1/series/quantidade-diaria", params={"medida": "abc"})
    assert r.status_code == 422 and r.json()["erro"]["detalhes"][0]["parametro"] == "medida"


def test_etag_responde_304_quando_nada_mudou(cliente):
    r1 = cliente.get("/api/v1/indicadores", params=PERIODO)
    etag = r1.headers["etag"]
    r2 = cliente.get("/api/v1/indicadores", params=PERIODO, headers={"If-None-Match": etag})
    assert r2.status_code == 304
    outro = cliente.get("/api/v1/indicadores", params={"inicio": "2026-01-03"}, headers={"If-None-Match": etag})
    assert outro.status_code == 200  # outra consulta, outra ETag


def test_sem_banco_publicado_responde_503(cliente, monkeypatch, tmp_path):
    from analitico.api import banco
    monkeypatch.setattr(banco, "ARQUIVO_PUBLICADO", tmp_path / "nao_existe.duckdb")
    r = cliente.get("/api/v1/indicadores")
    assert r.status_code == 503 and r.json()["erro"]["codigo"] == "SEM_DADOS_PUBLICADOS"
    assert r.headers["retry-after"] == "30"
