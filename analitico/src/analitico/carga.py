"""Carga completa: extrai as origens, recria as camadas staging e marts e roda os testes.

Uso:
  poetry run carga                    # carga incremental com verificação dia a dia
  poetry run carga --recarregar-tudo  # apaga o ledger copiado e recarrega desde o início
  poetry run carga --so-transformar   # não acessa a origem; só recalcula staging, marts e testes
  poetry run carga --a-cada 15        # fica rodando: uma carga a cada 15 minutos (Ctrl+C para parar)

Se todos os testes passarem, as marts são publicadas para a API (ver publicacao.py).
Se algo falhar, a API continua servindo a última versão boa, e o motivo fica em dados/ultima_carga.json.
"""
import argparse
import sys
import time
from datetime import datetime

from analitico.config import ARQUIVO_DW, PASTA_SQL, conectar_dw, hoje
from analitico.origens import estoque_supabase
from analitico.publicacao import gravar_status, publicar

DDL_META = """
create schema if not exists meta;
create sequence if not exists meta.seq_carga;
create table if not exists meta.cargas (
    id integer primary key default nextval('meta.seq_carga'),
    inicio timestamp, fim timestamp, data_referencia date, status varchar,
    dias_verificados integer, dias_recarregados integer, linhas_movimento integer,
    testes_com_falha integer, mensagem varchar
);
"""


def arquivos(pasta):
    return sorted((PASTA_SQL / pasta).glob("*.sql"))


def transformar(dw):
    """Executa, em ordem, os SQL das camadas. Cada arquivo recria um objeto."""
    for pasta in ("00_base", "10_staging", "20_marts"):
        for arq in arquivos(pasta):
            dw.execute(arq.read_text(encoding="utf-8"))


def testar(dw) -> list[tuple[str, int]]:
    """Cada teste é uma consulta que deve voltar vazia. Devolve [(teste, linhas_com_problema)]."""
    falhas = []
    for arq in arquivos("90_testes"):
        n = dw.execute(f"select count(*) from ({arq.read_text(encoding='utf-8').rstrip().rstrip(';')})").fetchone()[0]
        print(f"  {'OK   ' if n == 0 else 'FALHA'} {arq.stem}" + (f" ({n} linhas)" if n else ""))
        if n:
            falhas.append((arq.stem, n))
    return falhas


def main():
    ap = argparse.ArgumentParser(description="Carga do banco analítico")
    ap.add_argument("--recarregar-tudo", action="store_true")
    ap.add_argument("--so-transformar", action="store_true")
    ap.add_argument("--a-cada", type=float, metavar="MINUTOS", help="repete a carga a cada N minutos")
    args = ap.parse_args()
    if not args.a_cada:
        executar(args)
        return
    print(f"Modo contínuo: uma carga a cada {args.a_cada:g} min. Ctrl+C para parar.")
    try:
        while True:
            print(f"\n=== {datetime.now():%d/%m/%Y %H:%M:%S} ===")
            try:
                executar(args)
            except SystemExit:
                pass  # falha já registrada; a próxima rodada tenta de novo
            except Exception as e:
                print(f"Carga com erro: {e}", file=sys.stderr)
            args.recarregar_tudo = False
            time.sleep(args.a_cada * 60)
    except KeyboardInterrupt:
        print("\nModo contínuo encerrado.")


def executar(args):
    inicio = datetime.now()
    t0 = time.time()
    try:
        dw = conectar_dw()
    except Exception as e:  # tipicamente: outra carga em andamento segurando o arquivo
        gravar_status({"status": "ERRO", "inicio": inicio, "fim": datetime.now(), "publicado": False,
                       "mensagem": f"Não foi possível abrir o banco de trabalho: {str(e).strip()[:300]}"})
        raise SystemExit(f"Não foi possível abrir {ARQUIVO_DW}. Outra carga está rodando?\n{e}")
    dw.execute(DDL_META)
    ref = hoje()
    dw.execute("create or replace table meta.parametros as select ?::date as data_referencia", [ref])

    res = None
    status, mensagem, falhas, publicado = "OK", "", [], False
    try:
        if not args.so_transformar:
            print("Extraindo origem: estoque (Supabase)...")
            res = estoque_supabase.extrair(dw, recarregar_tudo=args.recarregar_tudo)
            dias = res.dias_recarregados
            faixa = f" ({dias[0]:%d/%m/%Y} a {dias[-1]:%d/%m/%Y})" if dias else ""
            print(f"  {res.dias_verificados} dias verificados, {len(dias)} recarregados{faixa}, "
                  f"{res.linhas_movimento} movimentos, {res.linhas_materiais} materiais, {res.linhas_saldo} saldos")
        print("Transformando (staging e marts)...")
        transformar(dw)
        print("Testes de consistência:")
        falhas = testar(dw)
        if falhas:
            status, mensagem = "FALHA_TESTES", ", ".join(f"{t} ({n})" for t, n in falhas)
    except Exception as e:  # registra a falha antes de sair
        status, mensagem = "ERRO", str(e).strip()[:500]
        raise
    finally:
        registro = {
            "inicio": inicio, "fim": datetime.now(), "data_referencia": ref, "status": status,
            "dias_verificados": res.dias_verificados if res else None,
            "dias_recarregados": len(res.dias_recarregados) if res else None,
            "linhas_movimento": res.linhas_movimento if res else None,
            "testes_com_falha": len(falhas), "mensagem": mensagem,
        }
        dw.execute(f"insert into meta.cargas ({', '.join(registro)}) values ({', '.join('?' * len(registro))})",
                   list(registro.values()))
        registro["id"] = dw.execute("select max(id) from meta.cargas").fetchone()[0]
        if status == "OK":
            publicar(dw)
            publicado = True
        dw.close()
        gravar_status({**registro, "publicado": publicado})

    if publicado:
        print(f"Carga OK em {time.time() - t0:.1f}s. Publicado para a API.")
    else:
        print(f"Carga {status}: NADA foi publicado; a API continua com a versão anterior.\nMotivo: {mensagem}",
              file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
