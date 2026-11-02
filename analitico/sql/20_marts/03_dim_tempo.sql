-- Um dia por linha, do primeiro movimento até a data de referência da carga (hoje).
create or replace table marts.dim_tempo as
select dia::date                                   as dia,
       year(dia)                                   as ano,
       month(dia)                                  as mes,
       strftime(dia, '%Y-%m')                      as ano_mes,
       isodow(dia)                                 as dia_semana,
       ['seg','ter','qua','qui','sex','sáb','dom'][isodow(dia)] as nome_dia_semana
  from generate_series(
         (select coalesce(min(dia), (select data_referencia from meta.parametros)) from staging.stg_movimentos),
         (select greatest(data_referencia, coalesce((select max(dia) from staging.stg_movimentos), data_referencia))
            from meta.parametros),
         interval 1 day) as t(dia);
