-- 1) TOTAIS GERAIS
-- Quantos movimentos (ledger) e tentativas recusadas existem, o maior seq do ledger,
-- quantas linhas de saldo existem e quantos saldos ficaram negativos.
-- Se ultimo_seq_mov for maior que movimentos, a diferença são números de seq queimados por inserts recusados.
-- Esperado: linhas_saldo = 16 (8 materiais x 2 almoxarifados) e saldos_negativos = 0.
select (select count(*) from estoque.sce_movimento_materiais) as movimentos,
       (select count(*) from estoque.sce_tentativas_requisicao) as tentativas,
       (select max(seq) from estoque.sce_movimento_materiais) as ultimo_seq_mov,
       (select count(*) from estoque.sce_estq_almoxs) as linhas_saldo,
       (select count(*) from estoque.sce_estq_almoxs where qtde_disponivel < 0) as saldos_negativos;

-- 2) MOVIMENTOS POR USUÁRIO E TIPO
-- Quantas linhas e quantas unidades cada usuário lançou, por tipo de movimento.
-- Esperado: o usuário C só com NR, e os usuários A e B só com RM, TRS e TRE.
select u.login, m.tipo_movimento, count(*) as linhas, sum(m.quantidade) as total
  from estoque.sce_movimento_materiais m
  join estoque.sce_usuarios u on u.codigo = m.usr_codigo
 group by 1, 2
 order by 1, 2;

-- 3) TRANSFERÊNCIAS: SAÍDA DA CENTRAL (TRS) CONTRA ENTRADA NO SATÉLITE (TRE), POR MATERIAL
-- Total que saiu da Central em transferência e total que chegou ao satélite, material por material.
-- Esperado: diferença 0 em todos os materiais.
select mat_codigo, trs, tre, trs - tre as diferenca
  from (select mat_codigo,
               coalesce(sum(quantidade) filter (where tipo_movimento = 'TRS'), 0) as trs,
               coalesce(sum(quantidade) filter (where tipo_movimento = 'TRE'), 0) as tre
          from estoque.sce_movimento_materiais
         group by 1) t
 order by 1;

-- 4) DIVERGÊNCIAS ENTRE LEDGER E SALDO
-- Compara, por material e almoxarifado, o saldo recalculado a partir do ledger
-- com o saldo mantido pelo trigger. Só aparecem linhas em que os dois valores diferem.
-- Esperado: nenhuma linha. É a principal verificação de integridade do teste.
select l.mat_codigo, l.almoxarifado, l.saldo_ledger, e.qtde_disponivel
  from (select mat_codigo, almoxarifado,
               sum(case when tipo_movimento in ('NR','TRE') then quantidade else -quantidade end) as saldo_ledger
          from estoque.sce_movimento_materiais
         group by 1, 2) l
  left join estoque.sce_estq_almoxs e
    on e.mat_codigo = l.mat_codigo and e.almoxarifado = l.almoxarifado
 where e.qtde_disponivel is distinct from l.saldo_ledger;

-- 5) SALDO ATUAL POR MATERIAL
-- Quanto cada material tem agora na Central e no satélite.
-- Central zerada com satélite ainda com saldo é normal. O problema aparece quando os dois zeram.
select m.codigo, m.nome,
       coalesce(c.qtde_disponivel, 0) as central,
       coalesce(s.qtde_disponivel, 0) as satelite
  from estoque.sco_materiais m
  left join estoque.sce_estq_almoxs c on c.mat_codigo = m.codigo and c.almoxarifado = 'CENTRAL'
  left join estoque.sce_estq_almoxs s on s.mat_codigo = m.codigo and s.almoxarifado = 'SATELITE'
 order by m.codigo;

-- 6) ENTRADAS DE ESTOQUE DO USUÁRIO C
-- Uma linha por transação de compra (NR): quando foi feita, de quantos materiais e o total de unidades.
-- Cada execução do SQL de entrada do usuário C aparece como uma linha.
select transacao_id, min(dt_geracao at time zone 'America/Fortaleza') as quando,
       count(*) as materiais, sum(quantidade) as total
  from estoque.sce_movimento_materiais
 where tipo_movimento = 'NR'
 group by 1
 order by 1;

-- 7) PEDIDOS RECUSADOS POR USUÁRIO E MOTIVO
-- Pedidos que não geraram movimento. unidades_pedidas é a soma do que foi pedido e não atendido.
-- SEM_ESTOQUE: o satélite e a Central estavam zerados.
-- PERDEU_DISPUTA: o banco recusou porque o saldo mudou durante o pedido (concorrência).
select u.login, t.motivo, count(*) as qtd, sum(t.quantidade_solicitada) as unidades_pedidas
  from estoque.sce_tentativas_requisicao t
  join estoque.sce_usuarios u on u.codigo = t.usr_codigo
 group by 1, 2
 order by 1, 2;

-- 8) PEDIDOS RECUSADOS POR MATERIAL
-- Quais materiais mais causaram recusas, ou seja, onde faltou estoque.
-- São os candidatos a uma nova entrada do usuário C.
select t.mat_codigo, mt.nome, count(*) as recusas
  from estoque.sce_tentativas_requisicao t
  join estoque.sco_materiais mt on mt.codigo = t.mat_codigo
 group by 1, 2
 order by 1;

-- 9) COMPRAS (NR) FEITAS COM A CENTRAL AINDA COM SALDO
-- Lista as compras que entraram quando a Central do material ainda tinha estoque (saldo_central_antes).
-- A regra é comprar só o que está zerado, e o SQL de entrada do C já filtra isso.
-- Esperado: nenhuma linha.
with c as (
  select seq, mat_codigo, tipo_movimento, quantidade, dt_geracao,
         coalesce(sum(case when tipo_movimento in ('NR','TRE') then quantidade else -quantidade end)
           over (partition by mat_codigo order by seq
                 rows between unbounded preceding and 1 preceding), 0) as saldo_central_antes
    from estoque.sce_movimento_materiais
   where almoxarifado = 'CENTRAL'
)
select seq, mat_codigo, quantidade, saldo_central_antes
  from c
 where tipo_movimento = 'NR' and saldo_central_antes > 0
 order by seq;

-- 10) TRANSFERÊNCIAS EM DOBRO (REPOSIÇÃO COM O SATÉLITE AINDA COM SALDO)
-- Lista as transferências (TRE) que entraram com o satélite já com estoque (saldo_satelite_antes).
-- Acontece quando dois usuários leem o satélite zerado ao mesmo tempo e os dois repõem.
-- Com a trava por material do gerador, esperado: nenhuma linha.
-- É informativa: o saldo continua correto mesmo quando aparecem linhas.
with s as (
  select seq, mat_codigo, tipo_movimento, quantidade, dt_geracao,
         coalesce(sum(case when tipo_movimento in ('NR','TRE') then quantidade else -quantidade end)
           over (partition by mat_codigo order by seq
                 rows between unbounded preceding and 1 preceding), 0) as saldo_satelite_antes
    from estoque.sce_movimento_materiais
   where almoxarifado = 'SATELITE'
)
select seq, mat_codigo, quantidade, saldo_satelite_antes
  from s
 where tipo_movimento = 'TRE' and saldo_satelite_antes > 0
 order by seq
