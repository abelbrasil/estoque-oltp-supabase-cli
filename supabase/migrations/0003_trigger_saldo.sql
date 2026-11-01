-- Aplica cada movimento ao saldo atual
create or replace function estoque.fn_atualiza_estoque()
returns trigger
language plpgsql
set search_path = estoque
as $$
begin
    if new.tipo_movimento in ('NR', 'TRE') then
        -- ENTRADA: cria a linha de saldo ou soma à existente
        insert into estoque.sce_estq_almoxs (mat_codigo, almoxarifado, qtde_disponivel, dt_atualizacao)
        values (new.mat_codigo, new.almoxarifado, new.quantidade, now())
        on conflict (mat_codigo, almoxarifado)
        do update set
            qtde_disponivel = estoque.sce_estq_almoxs.qtde_disponivel + excluded.qtde_disponivel,
            dt_atualizacao  = now();
    else
        -- SAÍDA (TRS, RM): checa e debita no mesmo UPDATE, o que evita saldo negativo sob concorrência
        update estoque.sce_estq_almoxs
           set qtde_disponivel = qtde_disponivel - new.quantidade,
               dt_atualizacao  = now()
         where mat_codigo   = new.mat_codigo
           and almoxarifado = new.almoxarifado
           and qtde_disponivel >= new.quantidade;

        if not found then
            raise exception
                'Saldo insuficiente ou inexistente: material %, almoxarifado %, tipo %, quantidade %',
                new.mat_codigo, new.almoxarifado, new.tipo_movimento, new.quantidade
                using errcode = 'check_violation';
        end if;
    end if;

    return new;
end;
$$;

drop trigger if exists trg_mov_atualiza_estoque on estoque.sce_movimento_materiais;

create trigger trg_mov_atualiza_estoque
after insert on estoque.sce_movimento_materiais
for each row
execute function estoque.fn_atualiza_estoque();
