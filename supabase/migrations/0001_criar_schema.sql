create schema if not exists estoque;
comment on schema estoque is 'Teste OLTP de estoque hospitalar: ledger + saldo mantido por trigger';

-- Schema fechado para a API: só conexão direta (scripts, painel, CLI) acessa.
revoke all on schema estoque from public;
revoke all on schema estoque from anon, authenticated;
alter default privileges in schema estoque revoke all on tables    from anon, authenticated;
alter default privileges in schema estoque revoke all on functions from anon, authenticated;
alter default privileges in schema estoque revoke all on sequences from anon, authenticated;
