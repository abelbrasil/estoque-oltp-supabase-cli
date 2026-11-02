import type { ReactNode } from "react";
import type { ErroApi } from "../api";

export function Secao({ titulo, subtitulo, children, acao }: { titulo: string; subtitulo?: string; children: ReactNode; acao?: ReactNode }) {
  return (
    <section className="secao">
      <div className="secao-topo">
        <div>
          <h2>{titulo}</h2>
          {subtitulo && <p className="sutil">{subtitulo}</p>}
        </div>
        {acao}
      </div>
      {children}
    </section>
  );
}

export function Aviso({ erro }: { erro: ErroApi }) {
  const detalhes = Array.isArray(erro.detalhes)
    ? (erro.detalhes as { parametro: string; problema: string }[]).map((d) => `${d.parametro}: ${d.problema}`).join(" · ")
    : null;
  return (
    <div className="aviso" role="alert">
      <strong>⚠ {erro.message}</strong>
      {detalhes && <div className="sutil">{detalhes}</div>}
    </div>
  );
}

export function Carregando({ ativo, children }: { ativo: boolean; children: ReactNode }) {
  return <div className={ativo ? "carregando" : undefined} aria-busy={ativo}>{children}</div>;
}

export function Bolinha({ cor }: { cor: string }) {
  return <span className="bolinha" style={{ background: cor }} aria-hidden />;
}
