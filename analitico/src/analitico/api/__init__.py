"""API REST dos dados agregados. `poetry run api` sobe o servidor (padrão: http://127.0.0.1:8000)."""
import argparse


def main():
    import uvicorn

    from analitico.config import API_HOST, API_PORTA

    ap = argparse.ArgumentParser(description="Sobe a API do painel de estoque")
    ap.add_argument("--host", default=API_HOST, help="0.0.0.0 expõe na rede local; o padrão só aceita esta máquina")
    ap.add_argument("--porta", type=int, default=API_PORTA)
    ap.add_argument("--recarregar", action="store_true", help="reinicia ao editar o código (desenvolvimento)")
    args = ap.parse_args()
    uvicorn.run("analitico.api.app:app", host=args.host, port=args.porta, reload=args.recarregar)
