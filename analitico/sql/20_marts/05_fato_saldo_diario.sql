-- Saldo no fim de cada dia, para cada material e almoxarifado (inclusive dias sem movimento).
-- valor_fim_dia usa o valor unitário atual do cadastro (a origem não tem histórico de preço).
create or replace table marts.fato_saldo_diario as
with grade as (
    select m.material_id, a.almoxarifado_id, t.dia
      from marts.dim_material m
      join marts.dim_almoxarifado a on a.origem = m.origem
     cross join marts.dim_tempo t
),
mov as (
    select material_id, almoxarifado_id, dia,
           sum(sinal * quantidade)                                  as variacao,
           sum(case when sinal > 0 then quantidade else 0 end)      as entradas,
           sum(case when sinal < 0 then quantidade else 0 end)      as saidas,
           sum(case when tipo = 'RM' then quantidade else 0 end)    as consumo,
           count(*) filter (where tipo = 'TRE')                     as reposicoes
      from marts.fato_movimento
     group by 1, 2, 3
)
select g.material_id, g.almoxarifado_id, g.dia,
       coalesce(mov.entradas, 0)   as entradas,
       coalesce(mov.saidas, 0)     as saidas,
       coalesce(mov.consumo, 0)    as consumo,
       coalesce(mov.reposicoes, 0) as reposicoes,
       sum(coalesce(mov.variacao, 0)) over (partition by g.material_id, g.almoxarifado_id order by g.dia) as saldo_fim_dia,
       saldo_fim_dia * m.valor_unitario as valor_fim_dia
  from grade g
  join marts.dim_material m using (material_id)
  left join mov using (material_id, almoxarifado_id, dia);
