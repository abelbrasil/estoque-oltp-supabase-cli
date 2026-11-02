-- Almoxarifados conhecidos. Por enquanto só Central e Satélite da origem estoque.
create or replace table marts.dim_almoxarifado as
select almoxarifado_id, origem, codigo,
       case codigo when 'CENTRAL' then 'Central' when 'SATELITE' then 'Satélite' else codigo end as nome
  from (select distinct origem, almoxarifado_id, almoxarifado as codigo from staging.stg_movimentos
        union
        select 'estoque', almoxarifado_id, replace(almoxarifado_id, 'estoque:', '') from staging.stg_saldo_origem);
