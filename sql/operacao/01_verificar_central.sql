-- Situação da Central por material. Execute antes de decidir uma entrada de estoque (02).
select m.codigo,
       m.nome,
       coalesce(c.qtde_disponivel, 0) as central,
       coalesce(s.qtde_disponivel, 0) as satelite,
       case when coalesce(c.qtde_disponivel, 0) = 0 then 'ZERADO' else 'ok' end as situacao_central,
       (select count(*)
          from estoque.sce_tentativas_requisicao t
         where t.mat_codigo = m.codigo
           and t.dt_tentativa > coalesce((select max(mv.dt_geracao)
                                            from estoque.sce_movimento_materiais mv
                                           where mv.mat_codigo = m.codigo
                                             and mv.tipo_movimento = 'NR'),
                                         '-infinity'::timestamptz)
       ) as pedidos_recusados_desde_ultima_nr
  from estoque.sco_materiais m
  left join estoque.sce_estq_almoxs c on c.mat_codigo = m.codigo and c.almoxarifado = 'CENTRAL'
  left join estoque.sce_estq_almoxs s on s.mat_codigo = m.codigo and s.almoxarifado = 'SATELITE'
 order by m.codigo
