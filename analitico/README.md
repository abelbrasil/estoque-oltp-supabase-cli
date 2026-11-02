# Painel de Estoque (projeto analítico)

Sistema de apoio à decisão sobre o estoque. Copia os dados das origens para um banco analítico
local (DuckDB), organiza em camadas, confere com a origem e mostra um dashboard diário (Streamlit).

Esta pasta é um projeto independente: tem o próprio `pyproject.toml` e pode virar um repositório
separado sem mudanças. A primeira origem é o banco OLTP de estoque do projeto vizinho.

## Indicadores da versão inicial (nível: dia)

| Indicador | De onde vem |
|---|---|
| Saldo atual por material e almoxarifado | `marts.mart_saldo_atual` |
| Valor financeiro em estoque (atual e variação no período) | `marts.mart_saldo_atual`, `marts.fato_saldo_diario` |
| Frequência de reposição do satélite (total, por dia, intervalo médio, por material) | `marts.fato_reposicao_satelite` |
| Quantidade por dia (saldo no fim do dia, consumo, entradas ou valor) | `marts.fato_saldo_diario` |

## Arquitetura

```
origem estoque (Supabase) ──► carga ──► dados/dw.duckdb ──► painel (Streamlit)
                                         raw      cópia fiel de cada origem (origem__tabela)
                                         staging  views padronizadas, chaves "origem:codigo"
                                         marts    dimensões, fatos e tabelas do painel
                                         meta     histórico das cargas
```

- **DuckDB**: banco analítico em um arquivo, gratuito, sem servidor. Ideal para rodar na própria máquina.
- **Camadas em SQL numerado** (`sql/`), executadas em ordem pela carga, no mesmo estilo do projeto de origem.
- **O painel só lê `marts`**: nunca consulta o banco de origem.

## Como a carga garante que nada se perde

A carga não lê o ledger "a partir do último `seq`", porque um `seq` menor pode ser confirmado
depois de um maior e seria pulado. Em vez disso:

1. Lê a origem em **uma única transação `REPEATABLE READ`**: ledger, saldo e cadastro vêm do mesmo instante,
   mesmo com os geradores A e B gravando ao mesmo tempo.
2. Calcula uma **impressão digital por dia** (linhas, soma dos `seq`, soma das quantidades) na origem e no DuckDB.
3. **Recarrega inteiro todo dia que difere** (ou que só existe de um dos lados). Normalmente é só o dia de hoje;
   um commit atrasado ou um reset da origem também são detectados e corrigidos.
4. Roda os **testes de consistência** (`sql/90_testes/`). O principal compara o saldo recalculado no DuckDB
   com o saldo que a origem mantém por trigger. Qualquer falha aparece no console, fica em `meta.cargas`
   e é mostrada no cabeçalho do painel.

## Pré-requisitos

Python 3.12 ou superior e [Poetry](https://python-poetry.org). O banco de origem já criado (projeto vizinho).

## Como usar

Todos os comandos são executados dentro desta pasta (`analitico/`).

### 1. Instalar

```bash
poetry install
```

### 2. Configurar

```bash
cp config.env.example config.env
```

Preencha `ESTOQUE_DB_URL` com a mesma `SUPABASE_DB_URL` do `credenciais.env` do projeto de origem.
O `config.env` tem senha e está no `.gitignore`: nunca versione.

### 3. Carregar

```bash
poetry run carga
```

Saída esperada: dias verificados e recarregados, e os testes com `OK`. Rode de novo sempre que quiser
atualizar o painel (é rápido, porque só os dias que mudaram são recarregados).

Outras opções:

```bash
poetry run carga --recarregar-tudo
```

```bash
poetry run carga --so-transformar
```

A primeira apaga o ledger copiado e recarrega desde o início. A segunda não acessa a origem: só recalcula
staging, marts e testes (útil ao editar os SQL).

### 4. Abrir o painel

```bash
poetry run painel
```

Abre em http://localhost:8501. Filtros: período, almoxarifado e materiais.
Se a carga estiver gravando no exato momento, o painel pede para atualizar a página em alguns segundos.

## Estrutura

```
src/analitico/config.py                  caminhos, fuso, conexão com o DuckDB
src/analitico/origens/estoque_supabase.py extrator da origem 1 (com a verificação dia a dia)
src/analitico/carga.py                    comando "carga": extrai, transforma e testa
src/analitico/painel/app.py               dashboard (Streamlit + Plotly)
sql/00_base/                              schemas
sql/10_staging/                           padronização da origem
sql/20_marts/                             dimensões, fatos e tabelas do painel
sql/90_testes/                            consultas que devem voltar vazias
dados/                                    dw.duckdb (fora do Git; pode ser apagado e recriado pela carga)
```

## Como incluir uma nova origem

1. Criar `src/analitico/origens/<origem>.py`, gravando em tabelas `raw.<origem>__<tabela>`.
2. Chamar o extrator em `carga.py`.
3. Acrescentar um `union all` nas views de `sql/10_staging/`, com `origem = '<origem>'` e chaves `'<origem>:' || codigo`.
4. Se o mesmo material existir em mais de uma origem com códigos diferentes, criar uma tabela de
   equivalência (de-para) e usá-la em `dim_material`.

## Limitações conhecidas

- **Histórico**: o painel é diário, mas a origem só tem os dias em que a simulação rodou. Com poucos dias,
  os gráficos ficam curtos.
- **Preço**: o valor financeiro usa o valor unitário atual do cadastro (a origem não guarda histórico de preço).
- **Unidades diferentes** (CX, UN, FR...): quantidades de materiais diferentes não são somadas nos indicadores;
  o valor em R$ é a medida comparável entre materiais.
