-- O saldo recalculado aqui a partir do ledger deve ser igual ao saldo que a origem mantém por trigger.
-- É a verificação ponta a ponta: se faltar ou sobrar movimento na carga, aparece aqui.
select coalesce(a.material_id, o.material_id) as material_id,
       coalesce(a.almoxarifado_id, o.almoxarifado_id) as almoxarifado_id,
       a.saldo as saldo_dw, o.saldo as saldo_origem
  from marts.mart_saldo_atual a
  full join staging.stg_saldo_origem o
    on o.material_id = a.material_id and o.almoxarifado_id = a.almoxarifado_id
 where coalesce(a.saldo, 0) <> coalesce(o.saldo, 0)
