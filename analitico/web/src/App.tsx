import { useCallback, useEffect, useMemo, useState } from "react";
import { obter, useApi } from "./api";
import type { Filtros, Indicadores, Medida, ReposicoesDiarias, ReposicoesPorMaterial, SaldoMaterial, Saude, SerieDiaria } from "./tipos";
import { corDoMaterial, useTema } from "./tema";
import { dataHoraBR, duracao, num } from "./formatos";
import { BarraFiltros, type Selecao } from "./componentes/BarraFiltros";
import { Cards } from "./componentes/Cards";
import { TabelaSaldo } from "./componentes/TabelaSaldo";
import { GraficoQuantidade, GraficoReposicoes, MEDIDAS } from "./componentes/Graficos";
import { Aviso, Bolinha, Carregando, Secao } from "./componentes/Comuns";

const INTERVALO_SAUDE_MS = 60_000;

/** Consulta /saude periodicamente. Quando uma nova carga é publicada, a versão muda e o painel se atualiza. */
function useSaude() {
  const [saude, setSaude] = useState<Saude | null>(null);
  const [falhou, setFalhou] = useState(false);
  const consultar = useCallback(() => {
    obter<Saude>("saude").then((s) => { setSaude(s); setFalhou(false); }).catch(() => setFalhou(true));
  }, []);
  useEffect(() => {
    consultar();
    const t = setInterval(consultar, INTERVALO_SAUDE_MS);
    return () => clearInterval(t);
  }, [consultar]);
  return { saude, falhou, consultar };
}

export default function App() {
  const tema = useTema();
  const { saude, falhou, consultar } = useSaude();
  const versao = saude?.carga_publicada?.id ?? null;

  const filtros = useApi<Filtros>("filtros", saude?.dados_publicados ? {} : null, versao);
  const [selecao, setSelecao] = useState<Selecao | null>(null);
  const [medida, setMedida] = useState<Medida>("saldo");

  // Primeira carga dos filtros: período padrão e tudo selecionado. Em nova versão, mantém o período dentro do disponível.
  useEffect(() => {
    const f = filtros.dados;
    if (!f) return;
    setSelecao((s) => {
      const { inicio, fim } = f.periodo_disponivel;
      if (!s) return { inicio: f.periodo_padrao.inicio, fim: f.periodo_padrao.fim, almoxarifados: f.almoxarifados.map((a) => a.id), materiais: [] };
      return { ...s, inicio: s.inicio < inicio ? inicio : s.inicio, fim: s.fim > fim ? fim : s.fim };
    });
  }, [filtros.dados]);

  const ordem = useMemo(() => filtros.dados?.materiais.map((m) => m.id) ?? [], [filtros.dados]);
  const cor = useCallback((id: string) => corDoMaterial(tema, ordem, id), [tema, ordem]);

  const params = selecao && {
    inicio: selecao.inicio, fim: selecao.fim, almoxarifado: selecao.almoxarifados,
    material: selecao.materiais.length ? selecao.materiais : undefined,
  };
  const indicadores = useApi<Indicadores>("indicadores", params, versao);
  const saldo = useApi<SaldoMaterial[]>("saldo-atual", params, versao);
  const serie = useApi<SerieDiaria>("series/quantidade-diaria", params && { ...params, medida }, versao);
  const repDia = useApi<ReposicoesDiarias>("reposicoes/diarias", params, versao);
  const repMat = useApi<ReposicoesPorMaterial>("reposicoes/por-material", params, versao);

  const almoxSel = filtros.dados?.almoxarifados.filter((a) => selecao?.almoxarifados.includes(a.id)) ?? [];

  return (
    <div className="pagina">
      <header className="cabecalho">
        <div>
          <h1>Dashboard Diário de Estoque</h1>
          <p className="sutil">Origem: estoque (Supabase) · nível de detalhe: dia</p>
        </div>
        <StatusCarga saude={saude} falhou={falhou} atualizar={consultar} />
      </header>

      {saude && !saude.dados_publicados && (
        <div className="aviso">⚠ Nenhuma carga publicada ainda. Rode <code>poetry run carga</code>.</div>
      )}
      {filtros.erro && <Aviso erro={filtros.erro} />}

      {filtros.dados && selecao && (
        <>
          <BarraFiltros opcoes={filtros.dados} selecao={selecao} mudar={setSelecao} cor={cor} />

          {indicadores.erro ? <Aviso erro={indicadores.erro} /> : indicadores.dados && (
            <Carregando ativo={indicadores.carregando}><Cards dados={indicadores.dados} /></Carregando>
          )}

          <Secao titulo="Saldo atual por material" subtitulo="Posição no último dia com dados, ordenada pelo valor em estoque.">
            {saldo.erro ? <Aviso erro={saldo.erro} /> : saldo.dados && (
              <Carregando ativo={saldo.carregando}><TabelaSaldo linhas={saldo.dados} almoxarifados={almoxSel} cor={cor} /></Carregando>
            )}
          </Secao>

          <Secao titulo="Quantidade por dia"
                 subtitulo="Cada material tem sua unidade (CX, UN, FR...): compare as linhas pela tendência. Para somar materiais, use o valor em R$."
                 acao={
                   <div className="segmentado" role="radiogroup" aria-label="Medida">
                     {(Object.keys(MEDIDAS) as Medida[]).map((m) => (
                       <button key={m} role="radio" aria-checked={medida === m} className={medida === m ? "ativo" : ""}
                               onClick={() => setMedida(m)}>{MEDIDAS[m]}</button>
                     ))}
                   </div>
                 }>
            {serie.erro ? <Aviso erro={serie.erro} /> : serie.dados && (
              <Carregando ativo={serie.carregando}><GraficoQuantidade dados={serie.dados} tema={tema} cor={cor} /></Carregando>
            )}
          </Secao>

          <Secao titulo="Frequência de reposição do satélite" subtitulo="Cada reposição é uma transferência da Central para o satélite (TRE).">
            {repDia.erro ? <Aviso erro={repDia.erro} /> : repDia.dados && (
              repDia.dados.itens.length === 0 ? <p className="sutil">Nenhuma reposição no período.</p> :
              <Carregando ativo={repDia.carregando}><GraficoReposicoes dados={repDia.dados} tema={tema} cor={cor} ordem={ordem} /></Carregando>
            )}
            {repMat.erro ? <Aviso erro={repMat.erro} /> : repMat.dados && repMat.dados.itens.length > 0 && (
              <Carregando ativo={repMat.carregando}>
                <div className="tabela-rolagem">
                  <table>
                    <thead><tr><th>Material</th><th className="num">Reposições</th><th className="num">Por dia</th>
                      <th className="num">Intervalo médio</th><th className="num">Qtde média reposta</th><th className="num">Última</th></tr></thead>
                    <tbody>
                      {repMat.dados.itens.map((i) => (
                        <tr key={i.material_id}>
                          <td><Bolinha cor={cor(i.material_id)} /> {i.material}</td>
                          <td className="num">{num(i.reposicoes)}</td><td className="num">{num(i.por_dia, 2)}</td>
                          <td className="num">{duracao(i.intervalo_medio_horas)}</td><td className="num">{num(i.quantidade_media)}</td>
                          <td className="num">{dataHoraBR(i.ultima)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Carregando>
            )}
          </Secao>
        </>
      )}
      <footer className="sutil">API: <a href="/docs" target="_blank" rel="noreferrer">documentação das rotas</a></footer>
    </div>
  );
}

function StatusCarga({ saude, falhou, atualizar }: { saude: Saude | null; falhou: boolean; atualizar: () => void }) {
  let classe = "status", texto = "Verificando…", detalhe: string | null = null;
  if (falhou) { classe += " ruim"; texto = "✕ API fora do ar"; detalhe = "Inicie com: poetry run api"; }
  else if (saude?.alerta) { classe += " atencao"; texto = "⚠ Última carga falhou"; detalhe = saude.alerta; }
  else if (saude?.carga_publicada) { classe += " bom"; texto = "✓ Dados conferidos com a origem";
    detalhe = saude.carga_publicada.fim ? `Carga de ${dataHoraBR(saude.carga_publicada.fim)}` : null; }
  return (
    <div className={classe} title={detalhe ?? undefined}>
      <div><strong>{texto}</strong>{detalhe && <div className="sutil limite">{detalhe}</div>}</div>
      <button onClick={atualizar} aria-label="Verificar agora">↻</button>
    </div>
  );
}
