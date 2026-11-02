-- Em cada transação, o que sai da Central (TRS) é igual ao que entra no satélite (TRE).
select transacao_id, material_id,
       sum(quantidade) filter (where tipo = 'TRS') as trs,
       sum(quantidade) filter (where tipo = 'TRE') as tre
  from marts.fato_movimento
 where tipo in ('TRS', 'TRE')
 group by 1, 2
having coalesce(trs, 0) <> coalesce(tre, 0)
