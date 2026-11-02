-- Todo movimento copiado da origem chega ao fato, e todo movimento tem material cadastrado.
select 'contagem' as problema
 where (select count(*) from raw.estoque__movimentos) <> (select count(*) from marts.fato_movimento)
union all
select 'sem material: ' || f.material_id
  from marts.fato_movimento f left join marts.dim_material m using (material_id)
 where m.material_id is null
