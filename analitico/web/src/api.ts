// Cliente da API: parâmetros repetidos, tempo limite, cancelamento e erros no formato da API.
import { useEffect, useState } from "react";

export class ErroApi extends Error {
  constructor(public status: number, public codigo: string, mensagem: string, public detalhes?: unknown) {
    super(mensagem);
  }
}

export type Params = Record<string, string | string[] | undefined>;

export async function obter<T>(caminho: string, params: Params = {}, sinal?: AbortSignal): Promise<T> {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined) continue;
    for (const x of Array.isArray(v) ? v : [v]) q.append(k, x);
  }
  const limite = AbortSignal.timeout(15000);
  let resp: Response;
  try {
    resp = await fetch(`/api/v1/${caminho}${q.size ? `?${q}` : ""}`, {
      headers: { Accept: "application/json" },
      signal: sinal ? AbortSignal.any([sinal, limite]) : limite,
    });
  } catch (e) {
    if (sinal?.aborted) throw e;
    if ((e as Error).name === "TimeoutError") throw new ErroApi(0, "TEMPO_ESGOTADO", "A API demorou demais para responder.");
    throw new ErroApi(0, "SEM_CONEXAO", "Não foi possível falar com a API. Ela está rodando (poetry run api)?");
  }
  const corpo = await resp.json().catch(() => null);
  if (!resp.ok) {
    const erro = corpo?.erro;
    throw new ErroApi(resp.status, erro?.codigo ?? "ERRO_HTTP", erro?.mensagem ?? `Erro HTTP ${resp.status}`, erro?.detalhes);
  }
  return corpo as T;
}

export interface Estado<T> { dados: T | null; erro: ErroApi | null; carregando: boolean }

/** Busca uma rota e refaz quando os parâmetros ou a versão dos dados mudam. Cancela buscas antigas. */
export function useApi<T>(caminho: string, params: Params | null, versao: unknown): Estado<T> {
  const [estado, setEstado] = useState<Estado<T>>({ dados: null, erro: null, carregando: true });
  const chave = JSON.stringify([caminho, params, versao]);
  useEffect(() => {
    if (params === null) return;
    const ctrl = new AbortController();
    setEstado((e) => ({ ...e, carregando: true }));
    obter<T>(caminho, params, ctrl.signal)
      .then((dados) => setEstado({ dados, erro: null, carregando: false }))
      .catch((erro) => {
        if (!ctrl.signal.aborted) setEstado((e) => ({ ...e, erro, carregando: false }));
      });
    return () => ctrl.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chave]);
  return estado;
}
