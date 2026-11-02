import { useMemo } from "react";
import type { EChartsCoreOption } from "echarts/core";
import type { Medida, ReposicoesDiarias, SerieDiaria } from "../tipos";
import { dataBR, diaMes, diasEntre, num } from "../formatos";
import { CORES, type Tema } from "../tema";
import { Grafico } from "./Grafico";
import { Bolinha } from "./Comuns";

// Legenda em HTML (abaixo do gráfico): quebra linha sozinha em qualquer largura de tela.
function Legenda({ itens }: { itens: { id: string; nome: string; cor: string }[] }) {
  return (
    <ul className="legenda">
      {itens.map((i) => <li key={i.id}><Bolinha cor={i.cor} />{i.nome}</li>)}
    </ul>
  );
}

// Atenção: o ECharts chama os formatadores com (valor, índice); por isso sempre (v) => ..., nunca a função direto.
function base(tema: Tema, dias: string[], formatoY: (v: number) => string): EChartsCoreOption {
  const c = CORES[tema];
  return {
    backgroundColor: "transparent",
    textStyle: { fontFamily: "inherit", color: c.texto2 },
    grid: { left: 8, right: 16, top: 16, bottom: 8, containLabel: true },
    xAxis: { type: "category", data: dias, axisLabel: { formatter: (v: string) => diaMes(v), color: c.texto2, hideOverlap: true },
             axisLine: { lineStyle: { color: c.eixo } }, axisTick: { show: false } },
    yAxis: { type: "value", axisLabel: { formatter: (v: number) => formatoY(v), color: c.texto2 },
             splitLine: { lineStyle: { color: c.grade } } },
  };
}

function dica(tema: Tema, formato: (v: number) => string, ocultarZeros: boolean) {
  const c = CORES[tema];
  return {
    trigger: "axis",
    axisPointer: { type: "line", lineStyle: { color: c.eixo } },
    backgroundColor: c.superficie, borderColor: c.eixo, textStyle: { color: c.texto },
    formatter: (itens: { axisValue: string; marker: string; seriesName: string; value: number }[]) => {
      const linhas = [...itens].filter((i) => !ocultarZeros || i.value).sort((a, b) => b.value - a.value)
        .map((i) => `${i.marker} ${i.seriesName} <b style="float:right;margin-left:16px">${formato(i.value)}</b>`);
      return `<b>${dataBR(itens[0].axisValue)}</b><br/>${linhas.join("<br/>") || "nenhuma"}`;
    },
  };
}

export const MEDIDAS: Record<Medida, string> = {
  saldo: "Saldo no fim do dia", consumo: "Consumo (RM)", entradas: "Entradas (NR e TRE)", valor: "Valor em estoque (R$)",
};

export function GraficoQuantidade({ dados, tema, cor }: { dados: SerieDiaria; tema: Tema; cor: (id: string) => string }) {
  const opcao = useMemo(() => {
    const dias = diasEntre(dados.periodo.inicio, dados.periodo.fim);
    const fmt = (v: number) => (dados.medida === "valor" ? `R$ ${num(v, 2)}` : num(v));
    return {
      ...base(tema, dias, (v) => num(v)),
      tooltip: dica(tema, fmt, false),
      series: dados.series.map((s) => {
        const porDia = new Map(s.pontos.map((p) => [p.dia, p.valor]));
        return {
          type: "line", name: `${s.material} (${s.unidade})`, color: cor(s.material_id),
          data: dias.map((d) => porDia.get(d) ?? null), lineStyle: { width: 2 },
          showSymbol: dias.length <= 14, symbolSize: 8, emphasis: { focus: "series" },
        };
      }),
    };
  }, [dados, tema, cor]);
  const legenda = dados.series.map((s) => ({ id: s.material_id, nome: `${s.material} (${s.unidade})`, cor: cor(s.material_id) }));
  return (
    <>
      <Grafico opcao={opcao} rotulo={`${MEDIDAS[dados.medida]} por dia e material`} />
      <Legenda itens={legenda} />
    </>
  );
}

export function GraficoReposicoes({ dados, tema, cor, ordem }: { dados: ReposicoesDiarias; tema: Tema; cor: (id: string) => string; ordem: string[] }) {
  const opcao = useMemo(() => {
    const dias = diasEntre(dados.periodo.inicio, dados.periodo.fim);
    const mats = [...new Map(dados.itens.map((i) => [i.material_id, i.material])).entries()]
      .sort((a, b) => ordem.indexOf(a[0]) - ordem.indexOf(b[0]));
    return {
      ...base(tema, dias, (v) => num(v)),
      yAxis: { ...(base(tema, dias, (v) => num(v)).yAxis as object), minInterval: 1 },
      tooltip: dica(tema, (v) => num(v), true),
      series: mats.map(([id, nome]) => {
        const porDia = new Map(dados.itens.filter((i) => i.material_id === id).map((i) => [i.dia, i.reposicoes]));
        return {
          type: "bar", stack: "reposicoes", name: nome, color: cor(id), barMaxWidth: 28,
          itemStyle: { borderColor: CORES[tema].superficie, borderWidth: 1 },
          data: dias.map((d) => porDia.get(d) ?? 0),
        };
      }),
    };
  }, [dados, tema, cor, ordem]);
  const legenda = [...new Map(dados.itens.map((i) => [i.material_id, i.material])).entries()]
    .sort((a, b) => ordem.indexOf(a[0]) - ordem.indexOf(b[0]))
    .map(([id, nome]) => ({ id, nome, cor: cor(id) }));
  return (
    <>
      <Grafico opcao={opcao} altura={280} rotulo="Reposições do satélite por dia e material" />
      <Legenda itens={legenda} />
    </>
  );
}
