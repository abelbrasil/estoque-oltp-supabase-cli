-- Saldo atual como a origem o mantém (trigger). Serve para conferir o saldo recalculado aqui.
create or replace view staging.stg_saldo_origem as
select 'estoque:' || mat_codigo       as material_id,
       'estoque:' || almoxarifado     as almoxarifado_id,
       qtde_disponivel                as saldo
  from raw.estoque__saldo;
