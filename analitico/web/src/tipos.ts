// Espelho dos esquemas da API (ver /docs).
export interface Periodo { inicio: string; fim: string; dias: number }
export interface CargaInfo { id?: number | null; status: string; fim?: string | null; data_referencia?: string | null; mensagem?: string | null }
export interface Saude { api: string; dados_publicados: boolean; carga_publicada: CargaInfo | null; ultima_carga: CargaInfo | null; alerta: string | null }
export interface Item { id: string; nome: string }
export interface MaterialItem extends Item { unidade: string; valor_unitario: number }
export interface Filtros { periodo_disponivel: Periodo; periodo_padrao: Periodo; almoxarifados: Item[]; materiais: MaterialItem[] }
export interface Indicadores {
  periodo: Periodo;
  valor_estoque: { atual: number; inicio_periodo: number; variacao_pct: number | null;
                   por_almoxarifado: { almoxarifado_id: string; almoxarifado: string; valor: number }[] };
  posicoes_zeradas: { zeradas: number; total: number };
  reposicoes_satelite: { total: number; media_por_dia: number; intervalo_medio_horas: number | null };
}
export interface SaldoMaterial {
  material_id: string; material: string; unidade: string; valor_unitario: number;
  por_almoxarifado: { almoxarifado_id: string; almoxarifado: string; saldo: number }[];
  total: number; valor: number;
}
export type Medida = "saldo" | "consumo" | "entradas" | "valor";
export interface SerieDiaria { medida: Medida; periodo: Periodo;
  series: { material_id: string; material: string; unidade: string; pontos: { dia: string; valor: number }[] }[] }
export interface ReposicoesDiarias { periodo: Periodo; itens: { dia: string; material_id: string; material: string; reposicoes: number }[] }
export interface ReposicoesPorMaterial { periodo: Periodo;
  itens: { material_id: string; material: string; reposicoes: number; por_dia: number;
           intervalo_medio_horas: number | null; quantidade_media: number; ultima: string }[] }
