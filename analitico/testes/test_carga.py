"""Garantias da carga: testes de consistência e publicação atômica."""
import duckdb

from analitico import carga
from analitico.config import ARQUIVO_PUBLICADO
from analitico.publicacao import publicar
from conftest import SALDO_ORIGEM, montar_banco


def test_divergencia_com_a_origem_e_detectada(cliente):
    errado = [(1, "CENTRAL", 41), *SALDO_ORIGEM[1:]]  # origem diz 41, o ledger diz 40
    dw = montar_banco(saldo_origem=errado)
    try:
        assert ("01_saldo_igual_origem", 1) in carga.testar(dw)
    finally:
        montar_banco().close()  # restaura para os demais testes


def test_publicacao_nao_interrompe_quem_esta_lendo(cliente):
    leitor = duckdb.connect(str(ARQUIVO_PUBLICADO), read_only=True)
    antes = leitor.execute("select count(*) from marts.fato_movimento").fetchone()[0]

    dw = montar_banco()
    dw.execute("delete from raw.estoque__movimentos where seq = 9")
    dw.execute("update raw.estoque__saldo set qtde_disponivel = 20 where mat_codigo = 1 and almoxarifado = 'SATELITE'")
    carga.transformar(dw)
    assert carga.testar(dw) == []
    publicar(dw)  # troca o arquivo enquanto o leitor está aberto
    dw.close()

    assert leitor.execute("select count(*) from marts.fato_movimento").fetchone()[0] == antes  # versão antiga, inteira
    leitor.close()
    novo = duckdb.connect(str(ARQUIVO_PUBLICADO), read_only=True)
    assert novo.execute("select count(*) from marts.fato_movimento").fetchone()[0] == antes - 1
    novo.close()

    dw = montar_banco()  # restaura
    publicar(dw)
    dw.close()


def test_api_atualiza_etag_quando_ha_nova_publicacao(cliente):
    etag = cliente.get("/api/v1/indicadores").headers["etag"]
    dw = montar_banco()
    publicar(dw)
    dw.close()
    r = cliente.get("/api/v1/indicadores", headers={"If-None-Match": etag})
    assert r.status_code == 200 and r.headers["etag"] != etag
