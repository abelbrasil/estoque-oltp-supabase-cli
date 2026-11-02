"""Painel de decisão (Streamlit). `poetry run painel` abre no navegador."""
import sys
from pathlib import Path


def main():
    from streamlit.web import cli

    app = Path(__file__).with_name("app.py")
    sys.argv = ["streamlit", "run", str(app), "--browser.gatherUsageStats=false",
                "--client.toolbarMode=minimal", *sys.argv[1:]]
    sys.exit(cli.main())
