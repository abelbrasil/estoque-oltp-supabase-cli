-- Um movimento por linha, com o valor financeiro do movimento.
create or replace table marts.fato_movimento as
select movimento_id, origem, transacao_id, material_id, almoxarifado_id, tipo, sinal,
       quantidade, valor_unitario, quantidade * valor_unitario as valor_total,
       usr_codigo, data_hora, dia
  from staging.stg_movimentos;
