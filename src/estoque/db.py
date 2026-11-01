"""Conexão com o banco, compartilhada pelos programas do projeto."""
import os
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parents[2]


def conectar():
    load_dotenv(RAIZ / "credenciais.env")
    url = os.environ.get("SUPABASE_DB_URL")
    if not url:
        raise SystemExit("SUPABASE_DB_URL não definida em credenciais.env")
    return psycopg2.connect(url)
