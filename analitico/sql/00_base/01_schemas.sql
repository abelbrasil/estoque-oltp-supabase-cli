-- Camadas do banco analítico.
-- raw:     cópia fiel de cada origem (gravada pelos extratores; nome origem__tabela)
-- staging: views que padronizam nomes, tipos e chaves, com a coluna origem
-- marts:   dimensões, fatos e tabelas prontas para o painel
-- meta:    histórico das cargas e parâmetros
create schema if not exists staging;
create schema if not exists marts;
