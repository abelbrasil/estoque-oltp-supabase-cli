-- Quem pode lançar o quê: NR só o perfil COMPRAS; RM, TRS e TRE só o perfil REQUISITANTE
create or replace function estoque.fn_valida_usuario_movimento()
returns trigger
language plpgsql
set search_path = estoque
as $$
declare
    v_perfil text;
    v_ativo  boolean;
begin
    select perfil, ativo into v_perfil, v_ativo
      from estoque.sce_usuarios
     where codigo = new.usr_codigo;

    if not found or not v_ativo then
        raise exception 'Usuário % inexistente ou inativo', new.usr_codigo
            using errcode = 'insufficient_privilege';
    end if;

    if new.tipo_movimento = 'NR' and v_perfil <> 'COMPRAS' then
        raise exception 'Usuário % (perfil %) não pode lançar NR', new.usr_codigo, v_perfil
            using errcode = 'insufficient_privilege';
    end if;

    if new.tipo_movimento <> 'NR' and v_perfil <> 'REQUISITANTE' then
        raise exception 'Usuário % (perfil %) não pode lançar %', new.usr_codigo, v_perfil, new.tipo_movimento
            using errcode = 'insufficient_privilege';
    end if;

    return new;
end;
$$;

drop trigger if exists trg_mov_valida_usuario on estoque.sce_movimento_materiais;

create trigger trg_mov_valida_usuario
before insert on estoque.sce_movimento_materiais
for each row
execute function estoque.fn_valida_usuario_movimento();

-- Ledger e tentativas são histórico: não aceitam UPDATE nem DELETE
create or replace function estoque.fn_bloqueia_alteracao()
returns trigger
language plpgsql
set search_path = estoque
as $$
begin
    raise exception 'Tabela % é histórico imutável: % não permitido', tg_table_name, tg_op
        using errcode = 'insufficient_privilege';
end;
$$;

drop trigger if exists trg_mov_imutavel on estoque.sce_movimento_materiais;
create trigger trg_mov_imutavel
before update or delete on estoque.sce_movimento_materiais
for each row execute function estoque.fn_bloqueia_alteracao();

drop trigger if exists trg_tent_imutavel on estoque.sce_tentativas_requisicao;
create trigger trg_tent_imutavel
before update or delete on estoque.sce_tentativas_requisicao
for each row execute function estoque.fn_bloqueia_alteracao();
