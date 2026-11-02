"""Aplicação FastAPI: rotas, tratamento de erros, CORS, cache por ETag e o painel compilado."""
import hashlib
import logging
import time

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from analitico.api.erros import ErroApi, tratar_erro_api, tratar_inesperado, tratar_validacao
from analitico.api.rotas import rotas
from analitico.config import API_ORIGENS_CORS, ARQUIVO_PUBLICADO, PASTA_WEB

log = logging.getLogger("analitico.api")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = FastAPI(
    title="API do Painel de Estoque",
    version="1.0.0",
    description="Dados agregados do estoque (nível dia), lidos do banco publicado pela carga. "
                "Todas as rotas do painel aceitam os filtros inicio, fim, almoxarifado e material.",
)
app.include_router(rotas)
app.add_exception_handler(ErroApi, tratar_erro_api)
app.add_exception_handler(RequestValidationError, tratar_validacao)
app.add_exception_handler(Exception, tratar_inesperado)
app.add_middleware(CORSMiddleware, allow_origins=API_ORIGENS_CORS, allow_methods=["GET"], allow_headers=["*"],
                   expose_headers=["ETag"])


@app.middleware("http")
async def cache_e_log(request: Request, chamar):
    """ETag = versão do banco publicado + URL. Se nada mudou desde a última carga, responde 304 sem consultar."""
    inicio = time.perf_counter()
    etag = None
    if request.method == "GET" and request.url.path.startswith("/api/v1/") and request.url.path != "/api/v1/saude":
        try:
            versao = ARQUIVO_PUBLICADO.stat().st_mtime_ns
            etag = '"' + hashlib.sha1(f"{versao}|{request.url.path}?{request.url.query}".encode()).hexdigest()[:20] + '"'
        except FileNotFoundError:
            pass
    if etag and request.headers.get("if-none-match") == etag:
        resposta = Response(status_code=304, headers={"ETag": etag})
    else:
        resposta = await chamar(request)
        if etag and resposta.status_code == 200:
            resposta.headers["ETag"] = etag
            resposta.headers["Cache-Control"] = "no-cache"
    if request.url.path.startswith("/api/"):
        log.info("%s %s -> %s (%.0f ms)", request.method, request.url.path + (f"?{request.url.query}" if request.url.query else ""),
                 resposta.status_code, (time.perf_counter() - inicio) * 1000)
    return resposta


# Painel compilado (web/dist). Montado por último para não encobrir /api e /docs.
if PASTA_WEB.is_dir():
    app.mount("/", StaticFiles(directory=PASTA_WEB, html=True), name="painel")
else:
    @app.get("/", include_in_schema=False)
    def inicio():
        return {"mensagem": "API no ar. Documentação em /docs. O painel ainda não foi compilado (cd web && npm run build)."}
