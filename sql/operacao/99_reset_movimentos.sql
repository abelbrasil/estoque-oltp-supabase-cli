-- ATENÇÃO: apaga movimentos, saldos e tentativas e reinicia a numeração.
-- Usuários e materiais são preservados.
truncate estoque.sce_movimento_materiais,
         estoque.sce_estq_almoxs,
         estoque.sce_tentativas_requisicao
restart identity
