# Painel de Estoque (projeto analítico)

Sistema de apoio à decisão sobre o estoque, para rodar na própria máquina. Três peças independentes:

```
 origem estoque        CARGA (Python)                  API (FastAPI)              PAINEL (React)
 (Supabase) ───────►  extrai, transforma, testa ───►  /api/v1/... JSON  ───────►  navegador
                       │                         publica   ▲
                       ▼                                   │ só leitura
                  dados/dw.duckdb ──(só se tudo OK)──► dados/publicado.duckdb
                  (trabalho)                            (troca atômica)
```

| Peça | O que faz | Comando |
|---|---|---|
| **Carga** | Copia a origem, recalcula as camadas, roda os testes e **publica só se tudo passar** | `poetry run carga` |
| **API** | Serve os dados agregados em rotas REST versionadas e também o painel compilado | `poetry run api` |
| **Painel** | Aplicação web (React + TypeScript + ECharts). Só consome a API | `npm run build` (uma vez) |

Esta pasta é um projeto independente: pode virar um repositório separado sem mudanças.

## Por que é robusto

- **Carga e API não disputam o banco.** A carga escreve em `dw.duckdb`. A API lê `publicado.duckdb`, uma cópia
  trocada de uma vez (`os.replace`) no fim de cada carga. A API nunca vê dado pela metade e nunca trava a carga.
- **Dado inconsistente não chega ao painel.** Se algum teste de consistência falhar, nada é publicado; a API continua
  com a última versão boa e o painel mostra o alerta (vindo de `dados/ultima_carga.json`).
- **Nenhum movimento se perde na cópia.** A origem é lida numa transação `REPEATABLE READ` e comparada dia a dia
  (linhas, soma dos `seq`, soma das quantidades); dias divergentes são recarregados. Cobre commits atrasados e reset da origem.
- **Contrato da API explícito.** Rotas em `/api/v1`, respostas tipadas (Pydantic), parâmetros validados e erros sempre
  no formato `{"erro": {"codigo", "mensagem", "detalhes"}}`. Documentação interativa em `/docs`.
- **Cache correto.** Cada resposta tem `ETag` ligada à versão publicada: o navegador recebe `304` enquanto não houver carga nova.
- **Painel se atualiza sozinho.** Consulta `/api/v1/saude` a cada minuto; quando uma nova carga é publicada, recarrega os dados.
- **Testado.** `poetry run pytest` confere as rotas contra valores calculados à mão, os erros, o ETag, a detecção de
  divergência e a troca do arquivo com leitores abertos.

## Pré-requisitos

- Python 3.12 ou superior e [Poetry](https://python-poetry.org)
- [Node.js](https://nodejs.org) 20 ou superior (só para compilar o painel)
- O banco de origem já criado (projeto vizinho, passos 1 e 2 do README dele)

## Primeira vez

Todos os comandos rodam dentro desta pasta (`analitico/`).

```bash
poetry install
```

```bash
cp config.env.example config.env
```

Preencha `ESTOQUE_DB_URL` no `config.env` com a mesma `SUPABASE_DB_URL` do `credenciais.env` do projeto de origem
(o `config.env` tem senha e está no `.gitignore`).

Compile o painel:

```bash
cd web && npm install && npm run build && cd ..
```

## Uso diário

Em dois terminais, dentro de `analitico/`:

```bash
poetry run carga --a-cada 15
```

```bash
poetry run api
```

Abra **http://127.0.0.1:8000** (painel) ou **http://127.0.0.1:8000/docs** (documentação da API).

O primeiro comando fica rodando e faz uma carga a cada 15 minutos (sem `--a-cada`, faz uma só e termina).
Se uma rodada falhar, a próxima tenta de novo e o painel mostra o aviso enquanto isso.

Outras opções da carga:

```bash
poetry run carga --recarregar-tudo
```

```bash
poetry run carga --so-transformar
```

A primeira apaga a cópia do ledger e recarrega desde o início. A segunda não acessa a origem: só recalcula as
camadas e os testes (útil ao editar os SQL).

## Rotas da API

Todas são `GET` e as do painel aceitam os filtros `inicio`, `fim` (AAAA-MM-DD), `almoxarifado` e `material`
(repita o parâmetro para vários valores, ex.: `?material=estoque:1&material=estoque:3`). Sem filtro: últimos 30 dias,
tudo selecionado.

| Rota | Retorna |
|---|---|
| `/api/v1/saude` | Situação da API, da carga publicada e da última carga (com alerta se falhou) |
| `/api/v1/filtros` | Período disponível, período padrão, almoxarifados e materiais |
| `/api/v1/indicadores` | Cards: valor em estoque (e variação no período), posições zeradas, reposições do satélite |
| `/api/v1/saldo-atual` | Saldo e valor atuais por material, separados por almoxarifado |
| `/api/v1/series/quantidade-diaria?medida=` | Uma série por material, um ponto por dia (`saldo`, `consumo`, `entradas` ou `valor`) |
| `/api/v1/reposicoes/diarias` | Reposições do satélite por dia e material |
| `/api/v1/reposicoes/por-material` | Frequência de reposição por material (total, por dia, intervalo médio, última) |

Exemplo:

```bash
curl "http://127.0.0.1:8000/api/v1/indicadores?inicio=2026-10-01&fim=2026-10-31&almoxarifado=estoque:SATELITE"
```

Códigos de resposta: `200` ok, `304` sem mudança desde a última consulta, `422` filtro inválido (o corpo diz qual),
`503` nenhuma carga publicada ainda.

Por padrão a API só aceita conexões desta máquina (`127.0.0.1`). Para abrir na rede local: `poetry run api --host 0.0.0.0`
(ainda não há autenticação; faça isso só em rede confiável).

## Desenvolvimento do painel

Com a API rodando (`poetry run api`), em outro terminal:

```bash
cd web && npm run dev
```

Abra http://localhost:5173: o painel recarrega a cada alteração e as chamadas `/api` vão para a API local.
Depois de mudar o painel, rode `npm run build` para a API servir a versão nova.

## Testes

```bash
poetry run pytest
```

Usam um banco montado com dados pequenos e conhecidos; não precisam da origem nem da API rodando.

## Estrutura

```
src/analitico/config.py                   caminhos, fuso, porta da API
src/analitico/origens/estoque_supabase.py  extrator da origem 1 (verificação dia a dia)
src/analitico/carga.py                     comando "carga": extrai, transforma, testa e publica
src/analitico/publicacao.py                cópia atômica das marts para a API e status da carga
src/analitico/api/                         API: rotas.py, esquemas.py (contrato), banco.py (filtros), erros.py, app.py
sql/00_base, 10_staging, 20_marts          camadas do modelo, executadas em ordem
sql/90_testes/                             consultas de consistência (devem voltar vazias)
web/                                       painel React + TypeScript (src/componentes, src/api.ts)
testes/                                    pytest da API e da carga
dados/                                     bancos e status (fora do Git; recriados pela carga)
```

## Como incluir uma nova origem

1. Criar `src/analitico/origens/<origem>.py`, gravando em tabelas `raw.<origem>__<tabela>`.
2. Chamar o extrator em `carga.py`.
3. Acrescentar um `union all` nas views de `sql/10_staging/`, com `origem = '<origem>'` e chaves `'<origem>:' || codigo`.
4. Se o mesmo material existir em mais de uma origem com códigos diferentes, criar uma tabela de equivalência (de-para)
   e usá-la em `dim_material`.

A API e o painel não mudam: eles leem só as marts.

## Limitações conhecidas

- **Histórico**: o painel é diário, mas a origem só tem os dias em que a simulação rodou.
- **Preço**: o valor financeiro usa o valor unitário atual do cadastro (a origem não guarda histórico de preço).
- **Unidades diferentes** (CX, UN, FR...): quantidades de materiais diferentes não são somadas; o valor em R$ é a medida comparável.
- **Paleta**: 8 cores fixas por material; a partir do 9º material, os demais aparecem em cinza.
