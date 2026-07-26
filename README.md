# Contract Management Analytics Platform

Plataforma analítica de portfólio para gestão de contratos, fornecedores e gastos. O projeto simula um ambiente corporativo de compras e consolida dados operacionais fictícios em uma base confiável para análise de exposição contratual, consumo, renovações, homologação de fornecedores e qualidade dos dados.

O desenvolvimento começa localmente com Python, arquivos em camadas e consultas SQL. A arquitetura foi planejada para uma migração incremental para AWS, utilizando Amazon S3, Glue, Athena e QuickSight, sem alterar as regras de negócio já validadas.

## Objetivos

- Construir um pipeline de dados ponta a ponta com as camadas `RAW → STAGING → CURATED`.
- Modelar contratos, pagamentos, fornecedores, RFIs/homologação e renovações em um esquema estrela.
- Analisar fornecedores tanto pela entidade legal (`CNPJ`) quanto pelo grupo econômico (`CNPJ8`).
- Produzir indicadores de saldo contratual, consumo, vencimentos, concentração de gastos, risco de homologação e qualidade dos dados.
- Manter o projeto reproduzível, documentado e preparado para evolução em nuvem.

## Perguntas de negócio

O modelo analítico responde, entre outras, às seguintes perguntas:

- Quanto de cada contrato já foi consumido e qual é seu saldo remanescente?
- Quais contratos estão vencidos ou próximos do fim de vigência?
- Quais grupos econômicos concentram maior valor contratado ou gasto?
- Quais fornecedores possuem pendências ou riscos no processo de homologação?
- Existem pagamentos sem contrato correspondente, após a vigência ou acima do valor contratado?

## Arquitetura de dados

```text
Fontes fictícias e dados cadastrais
    │
    ▼
RAW ── preservação dos arquivos de origem e metadados de carga
    │
    ▼
STAGING ── padronização de tipos, CNPJ, datas, valores e validações iniciais
    │
    ▼
CURATED ── dimensões, fatos, regras de negócio e tabelas de exceção
    │
    ▼
SQL e Dashboard ── métricas, análises e visualizações executivas
```

| Camada | Responsabilidade | Formato esperado |
|---|---|---|
| RAW | Preservar os dados recebidos, sem transformação de negócio. | CSV ou formato original |
| STAGING | Limpar, tipar, normalizar identificadores e registrar validações. | Preferencialmente Parquet |
| CURATED | Disponibilizar dimensões, fatos, indicadores e exceções para consumo analítico. | Parquet e views SQL |

## Estrutura do repositório

```text
.
├── 0.architecture/     # Diagramas e definições de arquitetura
├── 1.data/
│   ├── 1.raw/          # Arquivos de origem gerados ou recebidos
│   ├── 2.staging/      # Dados tratados tecnicamente
│   └── 3.curated/      # Modelo dimensional pronto para análise
├── 2.etl/              # Transformações, validações e utilitários do pipeline
├── 3.sql/              # Consultas analíticas, views e métricas
├── 4.dashboard/        # Especificações, medidas e evidências do dashboard
├── company_generator.py
├── contract_generator.py
├── spending_generator.py
└── Contract_Management_Analytics_Project_Charter.docx
```

> A estrutura será refinada ao longo da fase de fundação para separar código em `src/`, testes, documentação e notebooks, preservando as mesmas responsabilidades de cada camada.

## Fontes de dados

Os dados são inteiramente fictícios e gerados internamente para fins de portfólio.

| Fonte | Arquivo atual | Chave principal | Conteúdo |
|---|---|---|---|
| Cadastro de fornecedores | `1.data/1.raw/empresas.csv` | CNPJ | Razão social, porte, capital, faturamento e indicadores financeiros simulados |
| Contratos | `1.data/1.raw/contratos_ficticios.csv` | Código do contrato | Fornecedor, escopo, vigência, valores, saldo e status |
| Pagamentos | `1.data/1.raw/spending_ficticio.csv` | Código do pagamento | Contrato, fornecedor, data e valor pago |
| RFI / homologação | Planejado | ID de RFI | Status, prazo, categoria e pontuação do fornecedor |
| Renovações | Planejado | ID de renovação | Previsão, decisão, responsável e status da renovação |

## Modelo dimensional planejado

| Tabela | Tipo | Granularidade |
|---|---|---|
| `dim_supplier` | Dimensão | Uma entidade legal de fornecedor por CNPJ |
| `dim_economic_group` | Dimensão | Um grupo econômico por CNPJ8 |
| `dim_contract` | Dimensão | Um contrato formalizado |
| `dim_calendar` | Dimensão | Uma linha por data |
| `dim_category` | Dimensão | Uma categoria de compras |
| `fact_spending` | Fato | Um evento de pagamento/gasto |
| `fact_rfi` | Fato | Um evento de RFI ou homologação |
| `fact_renewal` | Fato | Um evento de renovação contratual |
| `fact_contract_snapshot` | Fato | Fotografia periódica de saldo e status do contrato |

As tabelas fato não devem ser relacionadas diretamente no dashboard. As análises devem utilizar dimensões compartilhadas ou views curadas para cada métrica.

## Indicadores iniciais

- Contratos ativos, valor contratado e contratos próximos do vencimento.
- Gasto total, saldo contratual e percentual de consumo.
- Alertas de consumo acelerado e contratos sobreconsumidos.
- Grupos econômicos ativos e fornecedores com maior concentração de gasto.
- Histórico e status de renovações.
- Risco de homologação e indicadores financeiros de fornecedores.
- Pagamentos sem contrato, pagamentos após a vigência e falhas de integridade.

## Como executar a geração dos dados

Pré-requisitos: Python 3 e as bibliotecas `pandas`, `numpy` e `python-dateutil`.

Execute os scripts na ordem abaixo, a partir da raiz do projeto:

```powershell
python company_generator.py
python contract_generator.py
python spending_generator.py
```

Os arquivos serão gravados em `1.data/1.raw/`. Os geradores utilizam dados aleatórios; antes de uma execução reproduzível completa, as sementes e os parâmetros de cenário serão centralizados.

## Qualidade e governança

- A camada RAW deve preservar o arquivo original e registrar fonte, data de carga, quantidade de linhas e, quando aplicável, checksum.
- `CNPJ` e `CNPJ8` devem ser tratados como texto, preservando zeros à esquerda.
- Registros não correspondidos não devem ser descartados: devem compor saídas explícitas de exceção.
- Cada métrica deve ter fórmula, granularidade, tabelas-fonte e critério de atualização documentados.
- O repositório deve conter apenas dados públicos ou fictícios; dados corporativos confidenciais não fazem parte do escopo.

## Roadmap

1. **Fundação:** organizar repositório, ambiente Python, dependências e documentação.
2. **Exploração cadastral:** documentar os campos de fornecedor relevantes e suas limitações.
3. **Geração de fontes:** criar contratos, pagamentos, RFI e renovações coerentes, incluindo anomalias controladas.
4. **RAW e STAGING:** registrar cargas, padronizar campos e validar esquemas.
5. **Supplier master:** construir `dim_supplier`, `dim_economic_group` e o mapeamento CNPJ/CNPJ8.
6. **CURATED:** publicar dimensões, fatos, reconciliações financeiras e tabelas de exceção.
7. **SQL e métricas:** criar consultas reutilizáveis, views e dicionário de métricas.
8. **Dashboard:** entregar páginas executivas para contratos, gastos, renovações, fornecedores e qualidade.
9. **AWS:** migrar gradualmente armazenamento para S3, transformações para Glue, consultas para Athena e BI para QuickSight.

## Próximos passos

- Criar a transformação de staging para fornecedores e normalizar CNPJ/CNPJ8.
- Definir os contratos de dados das fontes de RFI e renovações.
- Implementar validações de unicidade, completude, integridade referencial e reconciliação financeira.
- Criar o primeiro modelo dimensional curado e as consultas SQL de KPI.
- Documentar medidas e páginas do dashboard.

## Documento de referência

O planejamento detalhado, as decisões de arquitetura, o modelo de dados e o plano de migração estão no arquivo [Project Charter](Contract_Management_Analytics_Project_Charter.docx).
