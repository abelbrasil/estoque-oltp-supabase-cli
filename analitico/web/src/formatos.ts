const cache = new Map<number, Intl.NumberFormat>();
export function num(v: number | null | undefined, casas = 0): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "–";
  if (!cache.has(casas)) cache.set(casas, new Intl.NumberFormat("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas }));
  return cache.get(casas)!.format(v);
}
export const reais = (v: number | null | undefined) => (v === null || v === undefined ? "–" : `R$ ${num(v, 2)}`);
export const duracao = (h: number | null | undefined) =>
  h === null || h === undefined ? "–" : h >= 48 ? `${num(h / 24, 1)} dias` : `${num(h, 1)} h`;
export const dataBR = (iso: string) => iso.slice(0, 10).split("-").reverse().join("/");
export const diaMes = (iso: string) => iso.slice(8, 10) + "/" + iso.slice(5, 7);
export const dataHoraBR = (iso: string) => `${dataBR(iso)} ${iso.slice(11, 16)}`;

/** Todos os dias entre inicio e fim (AAAA-MM-DD), inclusive. */
export function diasEntre(inicio: string, fim: string): string[] {
  const dias: string[] = [];
  const d = new Date(inicio + "T00:00:00Z");
  const f = new Date(fim + "T00:00:00Z");
  while (d <= f) {
    dias.push(d.toISOString().slice(0, 10));
    d.setUTCDate(d.getUTCDate() + 1);
  }
  return dias;
}
export function somarDias(iso: string, n: number): string {
  const d = new Date(iso + "T00:00:00Z");
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}
