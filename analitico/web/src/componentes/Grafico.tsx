import { useEffect, useRef } from "react";
import * as echarts from "echarts/core";
import { BarChart, LineChart } from "echarts/charts";
import { GridComponent, LegendComponent, TooltipComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import type { EChartsCoreOption } from "echarts/core";

echarts.use([LineChart, BarChart, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer]);

export function Grafico({ opcao, altura = 360, rotulo }: { opcao: EChartsCoreOption; altura?: number; rotulo: string }) {
  const div = useRef<HTMLDivElement>(null);
  const grafico = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    const g = echarts.init(div.current!);
    grafico.current = g;
    const obs = new ResizeObserver(() => g.resize());
    obs.observe(div.current!);
    return () => { obs.disconnect(); g.dispose(); };
  }, []);

  useEffect(() => { grafico.current?.setOption(opcao, { notMerge: true }); }, [opcao]);

  return <div ref={div} role="img" aria-label={rotulo} style={{ width: "100%", height: altura }} />;
}
