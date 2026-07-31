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
| Empresas tratadas | `stg_empresas.py` | `stg_empresas_YYYYMMDD.parquet` |

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
```

Os geradores selecionam automaticamente a fonte versionada mais recente e preservam data e horário no nome dos arquivos. Execute-os na ordem acima para manter a coerência entre empresas, riscos, contratos, aditamentos e pagamentos.

## Qualidade e CI

```powershell
ruff check .
pytest
```

O GitHub Actions executa essas mesmas validações em pushes e pull requests para `main`.

## Regras relevantes

- Contratos só são gerados para fornecedores homologados com risco aprovado.
- Uma homologação de risco alto pode encerrar ciclos de renovação.
- Aditamentos registram renovações e aportes separadamente.
- Contratos vencidos conciliam gasto, valor total e saldo; contratos ativos podem ter pagamentos posteriores à data do snapshot.
- A staging padroniza identificadores, tipos e metadados de carga, além de separar registros inválidos em uma saída de exceções.

## Próximos passos

1. Criar staging para contratos, aditamentos, riscos e spending.
2. Construir dimensões e fatos na camada curated.
3. Implementar reconciliações, métricas SQL e dashboard.
4. Centralizar utilitários compartilhados de arquivos versionados e parâmetros de execução quando a estrutura de código migrar para um pacote `src/`.

Consulte o [Project Charter](docs/Contract_Management_Analytics_Project_Charter.docx) para o planejamento detalhado.
