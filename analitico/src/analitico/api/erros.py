"""Erros da API, sempre no mesmo formato: {"erro": {"codigo", "mensagem", "detalhes"}}."""
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ErroApi(Exception):
    def __init__(self, status: int, codigo: str, mensagem: str, detalhes=None, headers=None):
        self.status, self.codigo, self.mensagem, self.detalhes, self.headers = status, codigo, mensagem, detalhes, headers


def _corpo(codigo, mensagem, detalhes=None):
    return {"erro": {"codigo": codigo, "mensagem": mensagem, "detalhes": detalhes}}


async def tratar_erro_api(_: Request, e: ErroApi):
    return JSONResponse(_corpo(e.codigo, e.mensagem, e.detalhes), status_code=e.status, headers=e.headers)


async def tratar_validacao(_: Request, e: RequestValidationError):
    detalhes = [{"parametro": ".".join(str(p) for p in err["loc"][1:]), "problema": err["msg"]} for err in e.errors()]
    return JSONResponse(_corpo("PARAMETRO_INVALIDO", "Parâmetro inválido na requisição.", detalhes), status_code=422)


async def tratar_inesperado(_: Request, e: Exception):
    return JSONResponse(_corpo("ERRO_INTERNO", "Erro inesperado no servidor. Veja o log da API."), status_code=500)
