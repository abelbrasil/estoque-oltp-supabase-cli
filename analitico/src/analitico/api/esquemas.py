"""Formato das respostas (aparece na documentação em /docs)."""
from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel


class Periodo(BaseModel):
    inicio: date
    fim: date
    dias: int


class CargaInfo(BaseModel):
    id: int | None = None
    status: str
    fim: datetime | None = None
    data_referencia: date | None = None
    publicado: bool | None = None
    mensagem: str | None = None


class Saude(BaseModel):
    api: str
    dados_publicados: bool
    carga_publicada: CargaInfo | None
    ultima_carga: CargaInfo | None
    alerta: str | None


class Item(BaseModel):
    id: str
    nome: str


class MaterialItem(Item):
    unidade: str
    valor_unitario: float


class Filtros(BaseModel):
    periodo_disponivel: Periodo
    periodo_padrao: Periodo
    almoxarifados: list[Item]
    materiais: list[MaterialItem]


class ValorAlmox(BaseModel):
    almoxarifado_id: str
    almoxarifado: str
    valor: float


class ValorEstoque(BaseModel):
    atual: float
    inicio_periodo: float
    variacao_pct: float | None
    por_almoxarifado: list[ValorAlmox]


class PosicoesZeradas(BaseModel):
    zeradas: int
    total: int


class ReposicoesResumo(BaseModel):
    total: int
    media_por_dia: float
    intervalo_medio_horas: float | None


class Indicadores(BaseModel):
    periodo: Periodo
    valor_estoque: ValorEstoque
    posicoes_zeradas: PosicoesZeradas
    reposicoes_satelite: ReposicoesResumo


class SaldoAlmox(BaseModel):
    almoxarifado_id: str
    almoxarifado: str
    saldo: float


class SaldoMaterial(BaseModel):
    material_id: str
    material: str
    unidade: str
    valor_unitario: float
    por_almoxarifado: list[SaldoAlmox]
    total: float
    valor: float


class Medida(str, Enum):
    saldo = "saldo"
    consumo = "consumo"
    entradas = "entradas"
    valor = "valor"


class Ponto(BaseModel):
    dia: date
    valor: float


class Serie(BaseModel):
    material_id: str
    material: str
    unidade: str
    pontos: list[Ponto]


class SerieDiaria(BaseModel):
    medida: Medida
    periodo: Periodo
    series: list[Serie]


class ReposicaoDia(BaseModel):
    dia: date
    material_id: str
    material: str
    reposicoes: int


class ReposicoesDiarias(BaseModel):
    periodo: Periodo
    itens: list[ReposicaoDia]


class ReposicaoMaterial(BaseModel):
    material_id: str
    material: str
    reposicoes: int
    por_dia: float
    intervalo_medio_horas: float | None
    quantidade_media: float
    ultima: datetime


class ReposicoesPorMaterial(BaseModel):
    periodo: Periodo
    itens: list[ReposicaoMaterial]
