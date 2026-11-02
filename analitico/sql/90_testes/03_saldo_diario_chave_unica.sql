-- Uma linha por material, almoxarifado e dia.
select material_id, almoxarifado_id, dia, count(*)
  from marts.fato_saldo_diario group by 1, 2, 3 having count(*) > 1
