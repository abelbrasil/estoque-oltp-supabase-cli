-- Entrada de estoque (NR) feita pelo usuário C, somente para materiais com a Central zerada.
-- A quantidade é sorteada entre 500 e 1500 e o valor vem do cadastro do material.
-- Para outra faixa de quantidade, edite os números 500 e 1001 abaixo.
insert into estoque.sce_movimento_materiais
       (usr_codigo, mat_codigo, almoxarifado, tipo_movimento, quantidade, valor_unitario)
select (select codigo from estoque.sce_usuarios where login = 'C'),
       m.codigo,
       'CENTRAL',
       'NR',
       (500 + floor(random() * 1001))::numeric(14,3),
       m.valor_unitario
  from estoque.sco_materiais m
 where coalesce((select e.qtde_disponivel
                   from estoque.sce_estq_almoxs e
                  where e.mat_codigo = m.codigo and e.almoxarifado = 'CENTRAL'), 0) = 0
 order by m.codigo
returning seq, mat_codigo, quantidade, valor_unitario
