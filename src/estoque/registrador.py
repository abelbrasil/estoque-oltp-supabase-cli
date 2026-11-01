"""Registrador de auditoria: escreve em logs/oltp.log tudo o que acontece no banco (uma linha por interação)."""
import argparse
import re
import time
from datetime import datetime

import psycopg2

from estoque.db import RAIZ, conectar

ARQUIVO = RAIZ / "logs" / "oltp.log"
PADRAO_REF = re.compile(r"ref=(mov|tent)#(\d+)")

SQL = """
select to_char(x.dt at time zone 'America/Fortaleza', 'YYYY-MM-DD HH24:MI:SS.MS') as quando,
       x.login, x.tipo, x.almoxarifado, x.mat_codigo, x.material, x.qtd, x.situacao, x.tx,
       x.origem, x.seq
  from (
        select m.dt_geracao as dt, u.login, m.tipo_movimento::text as tipo, m.almoxarifado,
               m.mat_codigo, mt.nome as material, m.quantidade as qtd,
               'OK'::text as situacao, m.transacao_id as tx, 'mov'::text as origem, m.seq
          from estoque.sce_movimento_materiais m
          join estoque.sce_usuarios u   on u.codigo  = m.usr_codigo
          join estoque.sco_materiais mt on mt.codigo = m.mat_codigo
         where m.seq > %(mov)s
           and m.dt_geracao <= clock_timestamp() - make_interval(secs => %(atraso)s)
        union all
        select t.dt_tentativa, u.login, 'TENTATIVA'::text, t.almoxarifado,
               t.mat_codigo, mt.nome, t.quantidade_solicitada,
               t.motivo::text, null::bigint, 'tent'::text, t.seq
          from estoque.sce_tentativas_requisicao t
          join estoque.sce_usuarios u   on u.codigo  = t.usr_codigo
          join estoque.sco_materiais mt on mt.codigo = t.mat_codigo
         where t.seq > %(tent)s
           and t.dt_tentativa <= clock_timestamp() - make_interval(secs => %(atraso)s)
       ) x
 order by x.dt, x.origem, x.seq
"""


def formatar(r):
    quando, login, tipo, alm, mat, nome, qtd, sit, tx, origem, seq = r
    q = format(qtd.normalize(), "f")
    return (f"{quando} | usuario={login} | tipo={tipo} | almox={alm} | material={mat}-{nome} "
            f"| qtde={q} | situacao={sit} | tx={tx if tx else '-'} | ref={origem}#{seq}")


def posicao_inicial():
    ultimo = {"mov": 0, "tent": 0}
    if ARQUIVO.exists():
        for linha in ARQUIVO.read_text(encoding="utf-8").splitlines():
            m = PADRAO_REF.search(linha)
            if m:
                ultimo[m.group(1)] = max(ultimo[m.group(1)], int(m.group(2)))
    return ultimo


def abrir_conexao():
    conn = conectar()
    conn.set_session(readonly=True, autocommit=True)
    return conn, conn.cursor()


def main():
    ap = argparse.ArgumentParser(description="Escreve o log de auditoria a partir do banco")
    ap.add_argument("--intervalo", type=float, default=1.0, help="segundos entre leituras")
    ap.add_argument("--atraso", type=float, default=2.0, help="só registra eventos mais antigos que isso (s)")
    args = ap.parse_args()

    ARQUIVO.parent.mkdir(parents=True, exist_ok=True)
    ultimo = posicao_inicial()
    conn, cur = abrir_conexao()
    agora = lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with ARQUIVO.open("a", encoding="utf-8") as f:
        f.write(f"# registrador iniciado em {agora()} (retomando após mov#{ultimo['mov']} e tent#{ultimo['tent']})\n")
        f.flush()
        print(f"Registrador ativo, gravando em {ARQUIVO}. Ctrl+C para parar.", flush=True)
        try:
            while True:
                try:
                    cur.execute(SQL, {"mov": ultimo["mov"], "tent": ultimo["tent"], "atraso": args.atraso})
                    for r in cur.fetchall():
                        linha = formatar(r)
                        f.write(linha + "\n")
                        print(linha, flush=True)
                        ultimo[r[9]] = max(ultimo[r[9]], r[10])
                    f.flush()
                except psycopg2.Error as e:
                    print(f"Falha de leitura ({str(e).strip()}). Reconectando...", flush=True)
                    time.sleep(5)
                    conn, cur = abrir_conexao()
                time.sleep(args.intervalo)
        except KeyboardInterrupt:
            f.write(f"# registrador encerrado em {agora()}\n")
            print("\nRegistrador encerrado.", flush=True)
    conn.close()


if __name__ == "__main__":
    main()
