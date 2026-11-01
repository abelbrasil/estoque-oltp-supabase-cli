# Estoque OLTP no Supabase (teste de arquitetura, versão CLI)

Simulação de um sistema transacional de estoque hospitalar em Postgres (Supabase), criada e
gerenciada pela CLI. Valida escrita concorrente, saldo mantido por trigger e rastreabilidade
completa (auditoria) de cada interação.

## Como funciona

- **Ledger** `sce_movimento_materiais`: histórico imutável de movimentos. Cada linha tem o usuário que a lançou.
- **Saldo** `sce_estq_almoxs`: mantido por trigger a partir do ledger (Central e Satélite, por material).
- **Três usuários:**
  - **A e B** (perfil `REQUISITANTE`): geram requisições (`RM`) no satélite e as transferências
    (`TRS` + `TRE`) da Central para o satélite, em processos simultâneos.
  - **C** (perfil `COMPRAS`): único que lança entradas (`NR`), manualmente, por um SQL.
- **Regra de reposição:** o satélite repõe por transferência quando zera. Se a Central também
  está zerada, o pedido não gera movimento: é gravado em `sce_tentativas_requisicao` com o motivo
  `SEM_ESTOQUE`, e a Central só volta a ter saldo quando o usuário C executa a entrada.
- **O banco recusa:** saldo negativo, `NR` por quem não é `COMPRAS`, `RM`/`TRS`/`TRE` por `COMPRAS`,
  `UPDATE` ou `DELETE` no ledger e `NR` com valor menor ou igual a zero.
- **Trava por material:** o gerador usa `pg_advisory_xact_lock`, então pedidos do mesmo material
  são atendidos um de cada vez (evita transferência dupla e disputa de saldo entre A e B).
- **Log de auditoria** único, `logs/oltp.log`: uma linha por movimento ou tentativa, escrita pelo
  registrador a partir do banco (captura também o SQL manual do usuário C).

## Estrutura

```
supabase/migrations/   estrutura do banco, numerada (0001 a 0005), aplicada pela CLI
sql/operacao/          scripts de operação, numerados (01, 02, 03, 99)
src/estoque/           código Python: db, sql_runner, gerador, registrador
logs/                  log de auditoria e conferências (fora do Git)
pyproject.toml         dependências e comandos (Poetry)
.env.example           modelo das variáveis de ambiente
```

O schema do banco é `estoque`, fora da API pública do Supabase, com RLS ligado em todas as tabelas.

## Pré-requisitos

Python 3.12 ou superior, [Poetry](https://python-poetry.org), [Supabase CLI](https://supabase.com/docs/guides/local-development/cli/getting-started)
e uma conta no Supabase.

## Ordem de execução

Siga os passos nesta ordem. **O banco precisa estar criado (passos 1 e 2) antes de qualquer
script Python (passos 3 em diante).**

### 1. Criar o projeto no Supabase e vincular

```bash
supabase login
supabase orgs list
SENHA=$(openssl rand -base64 24 | tr -d '/+=')
printf 'SUPABASE_DB_PASSWORD=%s\n' "$SENHA" > credenciais.env
supabase projects create ESTOQUE_DDL_CLI --org-id <ID_DA_ORGANIZACAO> --db-password "$SENHA" --region sa-east-1
```

Anote o **REFERENCE ID** impresso, grave e vincule a pasta ao projeto:

```bash
printf 'SUPABASE_PROJECT_REF=%s\n' <REFERENCE_ID> >> credenciais.env
set -a; source credenciais.env; set +a
supabase link --project-ref "$SUPABASE_PROJECT_REF" -p "$SUPABASE_DB_PASSWORD"
```

Monte a connection string (Session pooler) para os scripts Python:

```bash
printf 'SUPABASE_DB_URL=%s\n' "$(sed "s#^postgresql://\([^@]*\)@#postgresql://\1:${SUPABASE_DB_PASSWORD}@#" supabase/.temp/pooler-url)" >> credenciais.env
```

O `credenciais.env` guarda senha e URL com senha e está no `.gitignore`: nunca versione.

### 2. Criar o banco (migrações)

```bash
set -a; source credenciais.env; set +a
supabase db push --linked -p "$SUPABASE_DB_PASSWORD"
```

Aplica, em ordem: schema `estoque` (0001), tabelas (0002), trigger do saldo (0003), regras de
usuário e imutabilidade (0004) e os dados de usuários e materiais (0005).

### 3. Preparar o ambiente Python

```bash
poetry config virtualenvs.in-project true
poetry install
poetry run sql -c "select login, perfil from estoque.sce_usuarios order by 1"
```

O último comando deve listar os usuários A, B e C.

### 4. Carga inicial de estoque (usuário C)

```bash
poetry run sql sql/operacao/02_entrada_estoque_C.sql
```

Repõe a Central de todos os materiais com saldo zerado (aqui, todos).

### 5. Executar a simulação

Em abas separadas do terminal, na pasta do projeto:

```bash
poetry run registrador
```

```bash
poetry run gerador --usuario A --duracao 8 --intervalo 2 --seed 101
```

```bash
poetry run gerador --usuario B --duracao 8 --intervalo 2 --seed 202
```

O registrador grava `logs/oltp.log`. Pare-o com Ctrl+C depois que A e B terminarem.
Parâmetros úteis do gerador: `--n` (número de requisições), `--duracao` (minutos), `--intervalo` (segundos), `--seed`.

### 6. Quando faltar estoque (usuário C)

Pedidos `SEM_ESTOQUE` aparecem no console dos geradores e no log. Veja o que está zerado e faça a entrada:

```bash
poetry run sql sql/operacao/01_verificar_central.sql
poetry run sql sql/operacao/02_entrada_estoque_C.sql
```

A entrada repõe só os materiais com a Central zerada, com quantidade sorteada entre 500 e 1500.

### 7. Conferir a consistência

```bash
poetry run sql sql/operacao/03_conferencias.sql | tee logs/conferencia.txt
```

Cada tabela vem precedida de um comentário com o que mostra e o que se espera ver.

### 8. Recomeçar do zero

Arquive o log **antes** de resetar (o registrador retoma pela numeração do próprio log):

```bash
mv logs/oltp.log logs/oltp_anterior.log
poetry run sql sql/operacao/99_reset_movimentos.sql
```

Apaga movimentos, saldos e tentativas e reinicia a numeração. Usuários e materiais são preservados.

## Parâmetros da simulação (`src/estoque/gerador.py`)

| Constante | Valor | Significado |
|---|---|---|
| `QTD_RM` | (1, 20) | Quantidade de cada requisição |
| `QTD_TRANSFERENCIA` | (200, 600) | Lote de reposição do satélite, limitado ao saldo da Central |
| `MAX_REPETICOES` | 2 | Repetições do pedido após perder uma disputa |

## Observações

- `seq` é identificador, não contador: insert recusado deixa buraco na numeração. Use `count(*)`.
- A conferência `03` compara o saldo do trigger com o saldo recalculado do ledger, confere
  `TRS` contra `TRE` e lista recusas, entradas do C e transferências em dobro.
- Resultado dos testes: 0 divergências entre ledger e saldo em todas as rodadas; com a trava por
  material, 0 disputas e 0 transferências em dobro sob carga sem intervalo.
