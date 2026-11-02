import { useEffect, useRef, useState } from "react";
import type { Filtros } from "../tipos";
import { somarDias } from "../formatos";
import { Bolinha } from "./Comuns";

export interface Selecao { inicio: string; fim: string; almoxarifados: string[]; materiais: string[] }

interface Props { opcoes: Filtros; selecao: Selecao; mudar: (s: Selecao) => void; cor: (id: string) => string }

export function BarraFiltros({ opcoes, selecao, mudar, cor }: Props) {
  const { inicio: dMin, fim: dMax } = opcoes.periodo_disponivel;
  const rapido = (dias: number | null) => {
    const ini = dias === null ? dMin : somarDias(dMax, -(dias - 1));
    mudar({ ...selecao, inicio: ini < dMin ? dMin : ini, fim: dMax });
  };
  const alternarAlm = (id: string) => {
    const atual = selecao.almoxarifados;
    const novo = atual.includes(id) ? atual.filter((a) => a !== id) : [...atual, id];
    if (novo.length) mudar({ ...selecao, almoxarifados: novo });
  };

  return (
    <div className="filtros">
      <div className="campo">
        <label>Período</label>
        <div className="linha">
          <input type="date" value={selecao.inicio} min={dMin} max={selecao.fim} aria-label="Data inicial"
                 onChange={(e) => e.target.value && mudar({ ...selecao, inicio: e.target.value })} />
          <span className="sutil">a</span>
          <input type="date" value={selecao.fim} min={selecao.inicio} max={dMax} aria-label="Data final"
                 onChange={(e) => e.target.value && mudar({ ...selecao, fim: e.target.value })} />
        </div>
        <div className="linha atalhos">
          {[7, 30, 90].map((n) => <button key={n} onClick={() => rapido(n)}>{n} dias</button>)}
          <button onClick={() => rapido(null)}>Tudo</button>
        </div>
      </div>

      <div className="campo">
        <label>Almoxarifado</label>
        <div className="linha">
          {opcoes.almoxarifados.map((a) => (
            <button key={a.id} className={`chip ${selecao.almoxarifados.includes(a.id) ? "ativo" : ""}`}
                    aria-pressed={selecao.almoxarifados.includes(a.id)} onClick={() => alternarAlm(a.id)}>
              {a.nome}
            </button>
          ))}
        </div>
      </div>

      <SeletorMateriais opcoes={opcoes} selecao={selecao} mudar={mudar} cor={cor} />
    </div>
  );
}

function SeletorMateriais({ opcoes, selecao, mudar, cor }: Props) {
  const [aberto, setAberto] = useState(false);
  const caixa = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const fechar = (e: MouseEvent) => { if (!caixa.current?.contains(e.target as Node)) setAberto(false); };
    document.addEventListener("mousedown", fechar);
    return () => document.removeEventListener("mousedown", fechar);
  }, []);
  const sel = selecao.materiais;
  const alternar = (id: string) =>
    mudar({ ...selecao, materiais: sel.includes(id) ? sel.filter((m) => m !== id) : [...sel, id] });
  const resumo = sel.length === 0 ? "Todos os materiais"
    : sel.length === 1 ? opcoes.materiais.find((m) => m.id === sel[0])?.nome : `${sel.length} materiais`;

  return (
    <div className="campo materiais" ref={caixa}>
      <label>Materiais</label>
      <button className="seletor" aria-expanded={aberto} onClick={() => setAberto(!aberto)}>
        <span>{resumo}</span><span aria-hidden>▾</span>
      </button>
      {aberto && (
        <div className="lista" role="listbox" aria-multiselectable>
          <button className="limpar" onClick={() => mudar({ ...selecao, materiais: [] })}>Mostrar todos</button>
          {opcoes.materiais.map((m) => (
            <label key={m.id} className="opcao">
              <input type="checkbox" checked={sel.includes(m.id)} onChange={() => alternar(m.id)} />
              <Bolinha cor={cor(m.id)} /> {m.nome} <span className="sutil">({m.unidade})</span>
            </label>
          ))}
        </div>
      )}
    </div>
  );
}
