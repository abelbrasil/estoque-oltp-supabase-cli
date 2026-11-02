import type { Item, SaldoMaterial } from "../tipos";
import { num, reais } from "../formatos";
import { Bolinha } from "./Comuns";

function Qtde({ v }: { v: number }) {
  return v === 0 ? <span className="zerado" title="Saldo zerado">⚠ 0</span> : <>{num(v)}</>;
}

export function TabelaSaldo({ linhas, almoxarifados, cor }: { linhas: SaldoMaterial[]; almoxarifados: Item[]; cor: (id: string) => string }) {
  const total = linhas.reduce((s, l) => s + l.valor, 0);
  return (
    <div className="tabela-rolagem">
      <table>
        <thead>
          <tr>
            <th>Material</th><th>Unid.</th>
            {almoxarifados.map((a) => <th key={a.id} className="num">{a.nome}</th>)}
            <th className="num">Total</th><th className="num">Valor unitário</th><th className="num">Valor em estoque</th>
          </tr>
        </thead>
        <tbody>
          {linhas.map((l) => (
            <tr key={l.material_id}>
              <td><Bolinha cor={cor(l.material_id)} /> {l.material}</td>
              <td>{l.unidade}</td>
              {almoxarifados.map((a) => (
                <td key={a.id} className="num"><Qtde v={l.por_almoxarifado.find((p) => p.almoxarifado_id === a.id)?.saldo ?? 0} /></td>
              ))}
              <td className="num"><Qtde v={l.total} /></td>
              <td className="num">{reais(l.valor_unitario)}</td>
              <td className="num forte">{reais(l.valor)}</td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr><td colSpan={almoxarifados.length + 4}>Total</td><td className="num forte">{reais(total)}</td></tr>
        </tfoot>
      </table>
    </div>
  );
}
