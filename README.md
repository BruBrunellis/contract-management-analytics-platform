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
| Pagamentos tratados | `stg_pagamentos.py` | `stg_pagamentos_YYYYMMDD_HHMMSS.parquet` |

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
python .\2.scr\2.etl\stg_pagamentos.py
```

Os geradores selecionam automaticamente a fonte versionada mais recente e preservam data e horário no nome dos arquivos. Execute-os na ordem acima para manter a coerência entre empresas, riscos, contratos, aditamentos e pagamentos.

### Execução orquestrada

Para gerar todas as fontes no mesmo lote, use o orquestrador:

```powershell
python .\2.scr\run_pipeline.py --interactive
```

Ou informe parâmetros sem interação:

```powershell
python .\2.scr\run_pipeline.py --qtd-empresas 500 --seed 42 --data-referencia 2026-07-31
```

O pipeline grava um `run_manifest_YYYYMMDD_HHMMSS.json` com os parâmetros,
arquivos produzidos e contagens de cada etapa. Um arquivo JSON também pode ser
informado com `--config caminho\para\cenario.json` para repetir cenários.

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

## Próximos passos

1. Criar staging para contratos, aditamentos, riscos e spending.
2. Construir dimensões e fatos na camada curated.
3. Implementar reconciliações, métricas SQL e dashboard.
4. Centralizar utilitários compartilhados de arquivos versionados e parâmetros de execução quando a estrutura de código migrar para um pacote `src/`.

Consulte o [Project Charter](docs/Contract_Management_Analytics_Project_Charter.docx) para o planejamento detalhado.
