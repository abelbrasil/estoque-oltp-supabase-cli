-- Saldo e valor financeiro atuais (último dia de fato_saldo_diario), prontos para o painel.
create or replace table marts.mart_saldo_atual as
select s.material_id, m.nome as material, m.unidade, s.almoxarifado_id, a.nome as almoxarifado,
       s.saldo_fim_dia as saldo, m.valor_unitario, s.valor_fim_dia as valor
  from marts.fato_saldo_diario s
  join marts.dim_material m using (material_id)
  join marts.dim_almoxarifado a using (almoxarifado_id)
 where s.dia = (select max(dia) from marts.dim_tempo);
