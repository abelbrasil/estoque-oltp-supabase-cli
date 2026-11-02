-- Materiais padronizados. material_id = origem:codigo, para que outras origens possam conviver.
create or replace view staging.stg_materiais as
select 'estoque'                      as origem,
       'estoque:' || codigo           as material_id,
       codigo                         as codigo_origem,
       nome,
       unidade_medida                 as unidade,
       valor_unitario
  from raw.estoque__materiais;
