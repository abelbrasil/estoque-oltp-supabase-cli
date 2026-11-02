create or replace table marts.dim_material as
select material_id, origem, codigo_origem, nome, unidade, valor_unitario
  from staging.stg_materiais;
