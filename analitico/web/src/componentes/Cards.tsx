import type { Indicadores } from "../tipos";
import { duracao, num, reais } from "../formatos";

function Card({ rotulo, valor, children }: { rotulo: string; valor: string; children?: React.ReactNode }) {
  return (
    <div className="card">
      <div className="rotulo">{rotulo}</div>
      <div className="valor">{valor}</div>
      <div className="detalhe">{children}</div>
    </div>
  );
}

export function Cards({ dados }: { dados: Indicadores }) {
  const { valor_estoque: v, posicoes_zeradas: z, reposicoes_satelite: r, periodo } = dados;
  const pct = v.variacao_pct;
  return (
    <div className="cards">
      <Card rotulo="Valor financeiro em estoque (atual)" valor={reais(v.atual)}>
        {pct !== null && (
          <div className={pct >= 0 ? "sobe" : "desce"}>
            {pct >= 0 ? "▲" : "▼"} {num(Math.abs(pct), 1)}% <span className="sutil">desde o início do período</span>
          </div>
        )}
        <div>{v.por_almoxarifado.map((a) => `${a.almoxarifado}: ${reais(a.valor)}`).join(" · ")}</div>
      </Card>
      <Card rotulo="Posições com saldo zerado (atual)" valor={num(z.zeradas)}>
        de {num(z.total)} posições (material × almoxarifado)
      </Card>
      <Card rotulo="Reposições do satélite no período" valor={num(r.total)}>
        média de {num(r.media_por_dia, 1)} por dia em {num(periodo.dias)} dias
      </Card>
      <Card rotulo="Intervalo médio entre reposições" valor={duracao(r.intervalo_medio_horas)}>
        tempo entre duas reposições do mesmo material
      </Card>
    </div>
  );
}
