"""Executa um arquivo .sql (ou um comando) no banco, em uma única transação.

Os comentários (linhas iniciadas por --) que antecedem cada comando são impressos acima do resultado.
Os comandos são separados pelo ';', então os arquivos não podem ter ';' dentro de texto ou comentário.
"""
import argparse
import sys
from pathlib import Path

import psycopg2

from estoque.db import conectar


def comandos(texto):
    """Devolve (comentarios, comando) para cada pedaço com SQL, separado pelo ';'."""
    for pedaco in texto.split(";"):
        linhas = [l.strip() for l in pedaco.splitlines() if l.strip()]
        if not any(not l.startswith("--") for l in linhas):
            continue
        comentarios = []
        for l in linhas:
            if l.startswith("--"):
                comentarios.append(l)
            else:
                break
        yield comentarios, pedaco.strip()


def imprimir(colunas, linhas):
    cel = [["" if v is None else str(v) for v in linha] for linha in linhas]
    larg = [max([len(c)] + [len(l[i]) for l in cel]) for i, c in enumerate(colunas)]
    print(" | ".join(c.ljust(larg[i]) for i, c in enumerate(colunas)))
    print("-+-".join("-" * w for w in larg))
    for l in cel:
        print(" | ".join(v.ljust(larg[i]) for i, v in enumerate(l)))
    print(f"({len(cel)} linha{'s' if len(cel) != 1 else ''})\n")


def main():
    p = argparse.ArgumentParser(description="Executa um arquivo SQL (ou um comando) no banco")
    p.add_argument("arquivo", nargs="?", help="arquivo .sql")
    p.add_argument("-c", "--comando", help="comando SQL direto")
    args = p.parse_args()
    if bool(args.arquivo) == bool(args.comando):
        p.error("informe um arquivo OU -c 'comando'")

    texto = Path(args.arquivo).read_text(encoding="utf-8") if args.arquivo else args.comando
    conn = conectar()
    cur = conn.cursor()
    try:
        for comentarios, stmt in comandos(texto):
            if comentarios:
                print("\n".join(comentarios))
            cur.execute(stmt)
            if cur.description:
                imprimir([d[0] for d in cur.description], cur.fetchall())
            else:
                print(cur.statusmessage + "\n")
        conn.commit()
    except psycopg2.Error as e:
        conn.rollback()
        print(f"ERRO: {str(e).strip()}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
