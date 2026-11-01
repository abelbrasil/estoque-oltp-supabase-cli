"""Gerador de requisições dos usuários A e B.

Cada pedido do usuário é uma transação e segue esta regra:
  0. Trava o material (pg_advisory_xact_lock): pedidos do mesmo material, de usuários
     diferentes, são atendidos um de cada vez. A trava termina no commit ou rollback.
  1. Lê o saldo do satélite.
  2. Se o satélite está zerado:
       2a. lê o saldo da Central; se também está zerado, registra a tentativa SEM_ESTOQUE
           (não gera movimento) e termina;
       2b. senão, transfere da Central para o satélite (TRS + TRE), limitado ao saldo da Central.
  3. Faz o RM no satélite, limitado ao saldo disponível.
  4. Confirma (commit).
Salvaguarda: se o trigger do banco recusar por saldo (CheckViolation), a transação é desfeita,
a tentativa é registrada como PERDEU_DISPUTA e o pedido é repetido (até MAX_REPETICOES vezes),
relendo o saldo. Com a trava do passo 0 isso não deve ocorrer entre A e B.
A NR (compra) não é feita aqui: é do usuário C, pelo SQL de entrada de estoque.
"""
import argparse
import random
import time
from datetime import datetime

import psycopg2
from psycopg2 import errors

from estoque.db import conectar

QTD_RM = (1, 20)                 # retirada pequena, como em um balcão
QTD_TRANSFERENCIA = (200, 600)   # lote de reposição do satélite
LOCK_MATERIAL = 1001             # classe da trava por material (pg_advisory_xact_lock)
MAX_REPETICOES = 2               # repetições do pedido depois de perder uma disputa

SQL_DIVERGENCIAS = """
select count(*)
  from (select m.mat_codigo, m.almoxarifado,
               sum(case when m.tipo_movimento in ('NR','TRE') then m.quantidade
                        else -m.quantidade end) as saldo_ledger
          from estoque.sce_movimento_materiais m
         group by 1, 2) l
  left join estoque.sce_estq_almoxs e
    on e.mat_codigo = l.mat_codigo and e.almoxarifado = l.almoxarifado
 where e.qtde_disponivel is distinct from l.saldo_ledger
"""


def saldo(cur, mat, alm):
    cur.execute(
        "select qtde_disponivel from estoque.sce_estq_almoxs "
        "where mat_codigo = %s and almoxarifado = %s",
        (mat, alm),
    )
    r = cur.fetchone()
    return int(r[0]) if r else 0


def inserir(cur, usr, mat, alm, tipo, qtd, valor):
    cur.execute(
        "insert into estoque.sce_movimento_materiais "
        "(usr_codigo, mat_codigo, almoxarifado, tipo_movimento, quantidade, valor_unitario) "
        "values (%s, %s, %s, %s, %s, %s)",
        (usr, mat, alm, tipo, qtd, valor),
    )


def registrar_tentativa(conn, cur, usr, mat, alm, qtd, motivo):
    """Grava o pedido recusado em uma transação própria, depois do rollback."""
    cur.execute(
        "insert into estoque.sce_tentativas_requisicao "
        "(usr_codigo, mat_codigo, almoxarifado, quantidade_solicitada, motivo) "
        "values (%s, %s, %s, %s, %s)",
        (usr, mat, alm, qtd, motivo),
    )
    conn.commit()


def atender(conn, cur, usr, mat, valor, qtd_pedida, rng):
    """Uma tentativa = uma transação. Devolve 'OK', 'SEM_ESTOQUE' ou 'PERDEU_DISPUTA'."""
    local = "SATELITE"
    try:
        # Passo 0: trava do material (liberada no commit/rollback)
        cur.execute("select pg_advisory_xact_lock(%s, %s)", (LOCK_MATERIAL, mat))

        # Passo 1: saldo do satélite
        sat = saldo(cur, mat, "SATELITE")

        # Passo 2: satélite zerado -> tenta repor pela Central
        if sat == 0:
            cen = saldo(cur, mat, "CENTRAL")
            if cen == 0:
                conn.rollback()  # encerra a transação e libera a trava
                registrar_tentativa(conn, cur, usr, mat, "CENTRAL", qtd_pedida, "SEM_ESTOQUE")
                return "SEM_ESTOQUE"
            transf = min(rng.randint(*QTD_TRANSFERENCIA), cen)
            local = "CENTRAL"
            inserir(cur, usr, mat, "CENTRAL", "TRS", transf, valor)
            inserir(cur, usr, mat, "SATELITE", "TRE", transf, valor)
            sat = transf

        # Passo 3: a requisição em si, limitada ao saldo do satélite
        local = "SATELITE"
        inserir(cur, usr, mat, "SATELITE", "RM", min(qtd_pedida, sat), valor)

        # Passo 4
        conn.commit()
        return "OK"
    except errors.CheckViolation:
        conn.rollback()
        registrar_tentativa(conn, cur, usr, mat, local, qtd_pedida, "PERDEU_DISPUTA")
        return "PERDEU_DISPUTA"


def requisitar(conn, cur, usr, mat, valor, qtd_pedida, rng):
    """Pedido do usuário: se perder uma disputa, ele repete (relendo o saldo), até MAX_REPETICOES."""
    disputas = 0
    while True:
        situacao = atender(conn, cur, usr, mat, valor, qtd_pedida, rng)
        if situacao != "PERDEU_DISPUTA" or disputas >= MAX_REPETICOES:
            if situacao == "PERDEU_DISPUTA":
                disputas += 1
            return situacao, disputas
        disputas += 1


def reconectar():
    for _ in range(5):
        try:
            conn = conectar()
            return conn, conn.cursor()
        except psycopg2.Error:
            time.sleep(5)
    raise SystemExit("Não foi possível reconectar ao banco.")


def resumo(inicio, contagem, cur, conn):
    cur.execute(SQL_DIVERGENCIAS)
    div = cur.fetchone()[0]
    conn.commit()
    dur = int(time.time() - inicio)
    print(f"--- Resumo: {dur}s | " + " | ".join(f"{k}: {v}" for k, v in contagem.items())
          + f" | divergências ledger x saldo: {div}", flush=True)


def main():
    ap = argparse.ArgumentParser(description="Gera requisições para um usuário (A ou B)")
    ap.add_argument("--usuario", required=True, choices=["A", "B"])
    ap.add_argument("--n", type=int, default=0, help="número de requisições (0 = sem limite)")
    ap.add_argument("--duracao", type=float, default=0, help="minutos (0 = até Ctrl+C)")
    ap.add_argument("--intervalo", type=float, default=2.0, help="segundos entre requisições")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--resumo-a-cada", type=int, default=50)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    conn = conectar()
    cur = conn.cursor()

    cur.execute("select codigo, perfil from estoque.sce_usuarios where login = %s and ativo",
                (args.usuario,))
    u = cur.fetchone()
    if not u or u[1] != "REQUISITANTE":
        raise SystemExit(f"Usuário {args.usuario} inexistente, inativo ou sem perfil REQUISITANTE.")
    usr = u[0]

    cur.execute("select codigo, nome, valor_unitario from estoque.sco_materiais order by codigo")
    materiais = {c: (n, v) for c, n, v in cur.fetchall()}
    conn.commit()
    codigos = list(materiais)

    contagem = {"OK": 0, "SEM_ESTOQUE": 0, "PERDEU_DISPUTA": 0, "DISPUTAS": 0, "ERRO": 0}
    inicio = time.time()
    fim = inicio + args.duracao * 60 if args.duracao else None
    total = 0

    print(f"Usuário {args.usuario} iniciado (seed={args.seed}). Ctrl+C para parar.", flush=True)
    try:
        while True:
            if args.n and total >= args.n:
                break
            if fim and time.time() >= fim:
                break
            mat = rng.choice(codigos)
            qtd = rng.randint(*QTD_RM)
            nome, valor = materiais[mat]
            try:
                situacao, disputas = requisitar(conn, cur, usr, mat, valor, qtd, rng)
            except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
                print(f"Conexão perdida ({str(e).strip()}). Reconectando...", flush=True)
                conn, cur = reconectar()
                contagem["ERRO"] += 1
                continue
            except psycopg2.Error as e:
                conn.rollback()
                contagem["ERRO"] += 1
                print(f"ERRO em {nome}: {str(e).strip()}", flush=True)
                continue
            contagem[situacao] += 1
            contagem["DISPUTAS"] += disputas
            total += 1
            hora = datetime.now().strftime("%H:%M:%S")
            extra = f" (após {disputas} disputa{'s' if disputas != 1 else ''})" if disputas else ""
            print(f"[{hora}] {args.usuario} #{total:<4} {nome[:30]:<30} pedido {qtd:>3} -> {situacao}{extra}",
                  flush=True)
            if args.resumo_a_cada and total % args.resumo_a_cada == 0:
                resumo(inicio, contagem, cur, conn)
            time.sleep(args.intervalo)
    except KeyboardInterrupt:
        conn.rollback()
        print("\nInterrompido pelo usuário.", flush=True)
    resumo(inicio, contagem, cur, conn)
    conn.close()


if __name__ == "__main__":
    main()
