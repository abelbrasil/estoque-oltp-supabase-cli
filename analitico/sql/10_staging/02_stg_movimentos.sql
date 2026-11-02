-- Movimentos do ledger. sinal: +1 entrada (NR, TRE), -1 saída (TRS, RM).
create or replace view staging.stg_movimentos as
select 'estoque'                      as origem,
       'estoque:' || seq              as movimento_id,
       seq,
       'estoque:' || transacao_id     as transacao_id,
       'estoque:' || mat_codigo       as material_id,
       'estoque:' || almoxarifado     as almoxarifado_id,
       almoxarifado,
       tipo_movimento                 as tipo,
       case when tipo_movimento in ('NR', 'TRE') then 1 else -1 end as sinal,
       quantidade,
       valor_unitario,
       usr_codigo,
       dt_local                       as data_hora,
       dia_local                      as dia
  from raw.estoque__movimentos;
