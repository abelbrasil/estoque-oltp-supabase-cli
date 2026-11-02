-- Uma linha por reposição do satélite (cada TRE), com o tempo desde a reposição anterior do mesmo material.
create or replace table marts.fato_reposicao_satelite as
select f.movimento_id, f.transacao_id, f.material_id, f.data_hora, f.dia, f.quantidade, f.valor_total,
       date_diff('minute', lag(f.data_hora) over (partition by f.material_id order by f.data_hora, f.movimento_id),
                 f.data_hora) / 60.0 as horas_desde_anterior
  from marts.fato_movimento f
  join marts.dim_almoxarifado a using (almoxarifado_id)
 where f.tipo = 'TRE' and a.codigo = 'SATELITE';
