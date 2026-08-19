# Contract Management Analytics Platform

Plataforma de dados fictícios para análise de contratos, fornecedores, riscos, aditamentos e gastos. O projeto organiza as fontes nas camadas **RAW → STAGING → CURATED**, com foco em qualidade de dados, rastreabilidade e análises de gestão contratual.

## Objetivos

- Simular um portfólio coerente de empresas, contratos, aditamentos, riscos e pagamentos.
- Padronizar e validar as fontes antes do consumo analítico.
- Preparar um modelo dimensional para métricas de consumo, saldo, vencimento, concentração, risco e qualidade de dados.
- Manter uma base reproduzível, testada e pronta para evolução em AWS.

## Estrutura

```text
1.data/
  1.raw/       # Arquivos CSV versionados gerados pelos scripts
  2.staging/   # Arquivos Parquet padronizados e exceções de qualidade
  3.curated/   # Camada analítica futura
2.scr/
  1.generator/ # Geradores das fontes primárias
  2.etl/       # Transformações da camada staging
  3.curated/   # Publicações do modelo dimensional
tests/         # Testes automatizados
docs/          # Project Charter e documentação complementar
```

## Fontes primárias

| Fonte | Gerador | Saída versionada |
|---|---|---|
| Empresas e grupos econômicos | `company_generator.py` | `empresas_YYYYMMDD_HHMMSS.csv` |
| Homologações e risco | `risk_generator.py` | `homologacoes_risco_YYYYMMDD_HHMMSS.csv` |
| Contratos e aditamentos | `contract_generator.py` | `contratos_ficticios_*.csv` e `aditamentos_*.csv` |
| Pagamentos | `spending_generator.py` | `spending_ficticio_YYYYMMDD_HHMMSS.csv` |
| Empresas tratadas | `stg_empresas.py` | `stg_empresas_YYYYMMDD_HHMMSS.parquet` |
| Contratos tratados | `stg_contratos.py` | `stg_contratos_YYYYMMDD_HHMMSS.parquet` |
| Aditamentos tratados | `stg_aditamentos.py` | `stg_aditamentos_YYYYMMDD_HHMMSS.parquet` |
| Pagamentos tratados | `stg_pagamentos.py` | `stg_pagamentos_YYYYMMDD_HHMMSS.parquet` |
| Homologações e risco tratados | `stg_homologacoes_risco.py` | `stg_homologacoes_risco_YYYYMMDD_HHMMSS.parquet` |
| Dimensão de fornecedores | `dim_fornecedores.py` | `dim_supplier_YYYYMMDD_HHMMSS.parquet` |
| Dimensão de grupos econômicos | `dim_fornecedores.py` | `dim_economic_group_YYYYMMDD_HHMMSS.parquet` |
| Dimensão de calendário | `dim_calendario_categoria.py` | `dim_calendar_YYYYMMDD_HHMMSS.parquet` |
| Dimensão de categorias | `dim_calendario_categoria.py` | `dim_category_YYYYMMDD_HHMMSS.parquet` |
| Dimensão de contratos | `dim_contratos_gastos.py` | `dim_contract_YYYYMMDD_HHMMSS.parquet` |
| Fato de pagamentos | `dim_contratos_gastos.py` | `fact_spending_YYYYMMDD_HHMMSS.parquet` |
| Fato de homologação e risco | `facts_risco_renovacao.py` | `fact_rfi_YYYYMMDD_HHMMSS.parquet` |
| Fato de renovação e aditamento | `facts_risco_renovacao.py` | `fact_renewal_YYYYMMDD_HHMMSS.parquet` |

Todos os dados são fictícios. Os arquivos CSV e Parquet gerados são ignorados pelo Git para que o repositório contenha código, testes e documentação.

## Execução local

Use Python 3.12 ou superior. A partir da raiz do projeto:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt

python .\2.scr\1.generator\company_generator.py
python .\2.scr\1.generator\risk_generator.py
python .\2.scr\1.generator\contract_generator.py
python .\2.scr\1.generator\spending_generator.py
python .\2.scr\2.etl\stg_empresas.py
python .\2.scr\2.etl\stg_contratos.py
python .\2.scr\2.etl\stg_aditamentos.py
python .\2.scr\2.etl\stg_pagamentos.py
python .\2.scr\2.etl\stg_homologacoes_risco.py
python .\2.scr\3.curated\dim_fornecedores.py
python .\2.scr\3.curated\dim_calendario_categoria.py
python .\2.scr\3.curated\dim_contratos_gastos.py
python .\2.scr\3.curated\facts_risco_renovacao.py
```

Os geradores selecionam automaticamente a fonte versionada mais recente e preservam data e horário no nome dos arquivos. Execute-os na ordem acima para manter a coerência entre empresas, riscos, contratos, aditamentos e pagamentos.

### Execução orquestrada

O fluxo recomendado separa a geração RAW da execução ETL. Primeiro, crie o snapshot
inicial do cenário:

```powershell
python .\2.scr\generate_raw.py `
  --scenario-id cenario_001 `
  --qtd-empresas 500 `
  --seed 42 `
  --data-referencia 2026-07-31
```

Em seguida, processe somente as fontes declaradas no manifesto criado:

```powershell
python .\2.scr\run_etl.py `
  --raw-manifest .\1.data\1.raw\cenario_001\<snapshot_id>\raw_manifest.json
```

Para evoluir esse cenário para uma nova data sem alterar o snapshot anterior:

```powershell
python .\2.scr\update_raw.py `
  --from-manifest .\1.data\1.raw\cenario_001\<snapshot_id>\raw_manifest.json `
  --data-referencia 2026-09-30 `
  --seed 99 `
  --probabilidade-novos-fornecedores 0.10 `
  --probabilidade-novos-contratos 0.50 `
  --probabilidade-novos-pagamentos 0.75
```

Execute `run_etl.py` novamente com o manifesto retornado pela atualização. Cada
processamento é gravado em diretórios próprios de staging e curated, e produz um
`etl_manifest.json` com o `source_snapshot_id` e o `pipeline_run_id`. O
`run_pipeline.py` continua disponível como atalho para gerar um cenário inicial e
processá-lo em uma única execução. Consulte [snapshots RAW](docs/raw_snapshots.md).

### Camada analítica DuckDB

Para publicar as views SQL sobre uma execução curated aprovada, informe o manifesto
ETL correspondente:

```powershell
python .\2.scr\4.analytics\build_analytics.py `
  --etl-manifest .\1.data\3.curated\<pipeline_run_id>\etl_manifest.json
```

O comando cria um banco local DuckDB por `pipeline_run_id`, com views de
fornecedores, contratos, pagamentos, renovações e qualidade. Consulte os
[contratos analíticos](docs/analytics_contracts.md).

## Qualidade e CI

```powershell
ruff check .
pytest
```

No Windows, o `pytest` cria um diretório temporário exclusivo para cada
execução em `.pytest_tmp` e o remove ao finalizar a sessão. Dessa forma, não
reutiliza nem tenta apagar uma pasta que possa estar bloqueada por outro
processo. O cache persistente do pytest fica desabilitado para evitar bloqueios
de `.pytest_cache`.

O GitHub Actions executa essas mesmas validações em pushes e pull requests para `main`.

## Regras relevantes

- Contratos só são gerados para fornecedores homologados com risco aprovado.
- Uma homologação de risco alto pode encerrar ciclos de renovação.
- Aditamentos registram renovações e aportes separadamente.
- Contratos vencidos conciliam gasto, valor total e saldo; contratos ativos podem ter pagamentos posteriores à data do snapshot.
- A staging padroniza identificadores, tipos e metadados de carga, além de separar registros inválidos em uma saída de exceções. Consulte os [contratos técnicos de staging](docs/staging_contracts.md).
- A camada curated publica dimensões de fornecedores, grupos econômicos, calendário, categorias e contratos, além dos fatos de pagamentos, risco e renovação. Consulte os [contratos técnicos curated](docs/curated_contracts.md).
- O pipeline publica um relatório de reconciliação e um índice consolidado de exceções curated por lote. Consulte o [quality gate curated](docs/curated_quality.md).

## Próximos passos

1. Construir dimensões e fatos na camada curated.
2. Implementar reconciliações, métricas SQL e dashboard.
3. Centralizar utilitários compartilhados de arquivos versionados e parâmetros de execução quando a estrutura de código migrar para um pacote `src/`.

Consulte o [Project Charter](docs/Contract_Management_Analytics_Project_Charter.docx) para o planejamento detalhado.
