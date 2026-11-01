-- Usuários do processo: A e B requisitam e transferem; C faz as compras (NR)
create table estoque.sce_usuarios (
    codigo      smallint    generated always as identity primary key,
    login       text        not null unique,
    nome        text        not null,
    perfil      text        not null check (perfil in ('REQUISITANTE','COMPRAS')),
    ativo       boolean     not null default true,
    dt_criacao  timestamptz not null default now()
);

-- Materiais (cadastro simplificado)
create table estoque.sco_materiais (
    codigo          integer       generated always as identity primary key,
    nome            text          not null,
    unidade_medida  text          not null default 'UN',
    valor_unitario  numeric(14,4) not null default 0 check (valor_unitario >= 0)
);

-- Ledger: cada linha é um movimento, sempre atribuído a um usuário
create table estoque.sce_movimento_materiais (
    seq             bigint        generated always as identity primary key,
    transacao_id    bigint        not null default txid_current(),
    usr_codigo      smallint      not null references estoque.sce_usuarios (codigo) on delete restrict,
    mat_codigo      integer       not null references estoque.sco_materiais (codigo) on delete restrict,
    almoxarifado    text          not null check (almoxarifado in ('CENTRAL','SATELITE')),
    tipo_movimento  text          not null check (tipo_movimento in ('NR','TRS','TRE','RM')),
    quantidade      numeric(14,3) not null check (quantidade > 0),
    valor_unitario  numeric(14,4) not null default 0 check (valor_unitario >= 0),
    dt_geracao      timestamptz   not null default clock_timestamp(),
    constraint ck_nr_valor_positivo check (tipo_movimento <> 'NR' or valor_unitario > 0)
);

-- Saldo atual por material e almoxarifado (mantido por trigger)
create table estoque.sce_estq_almoxs (
    seq              bigint        generated always as identity primary key,
    mat_codigo       integer       not null references estoque.sco_materiais (codigo) on delete restrict,
    almoxarifado     text          not null check (almoxarifado in ('CENTRAL','SATELITE')),
    qtde_disponivel  numeric(14,3) not null default 0 check (qtde_disponivel >= 0),
    dt_atualizacao   timestamptz   not null default now(),
    unique (mat_codigo, almoxarifado)
);

-- Pedidos que não puderam ser atendidos (não geram movimento no ledger)
create table estoque.sce_tentativas_requisicao (
    seq                  bigint        generated always as identity primary key,
    usr_codigo           smallint      not null references estoque.sce_usuarios (codigo) on delete restrict,
    mat_codigo           integer       not null references estoque.sco_materiais (codigo) on delete restrict,
    almoxarifado         text          not null check (almoxarifado in ('CENTRAL','SATELITE')),
    quantidade_solicitada numeric(14,3) not null check (quantidade_solicitada > 0),
    motivo               text          not null check (motivo in ('SEM_ESTOQUE','PERDEU_DISPUTA')),
    dt_tentativa         timestamptz   not null default clock_timestamp()
);

create index ix_mov_mat_alm on estoque.sce_movimento_materiais (mat_codigo, almoxarifado, dt_geracao);
create index ix_mov_usuario on estoque.sce_movimento_materiais (usr_codigo, dt_geracao);
create index ix_tent_usuario on estoque.sce_tentativas_requisicao (usr_codigo, dt_tentativa);

-- Segunda camada de proteção: RLS ligado em todas, sem políticas
alter table estoque.sce_usuarios              enable row level security;
alter table estoque.sco_materiais             enable row level security;
alter table estoque.sce_movimento_materiais   enable row level security;
alter table estoque.sce_estq_almoxs           enable row level security;
alter table estoque.sce_tentativas_requisicao enable row level security;
