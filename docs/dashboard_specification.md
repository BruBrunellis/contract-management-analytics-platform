# Especificação do dashboard executivo

## Decisão de ferramenta

O MVP será construído no **Power BI Desktop**, conectado em modo **Import** ao
banco DuckDB produzido por `build_analytics.py`. A escolha favorece a análise
interativa local, navegação entre páginas, filtros, drill-through e uma
apresentação de BI adequada ao portfólio.

O Power BI Service é o destino futuro de publicação. Como o banco DuckDB é
local, a atualização no serviço exigirá um gateway em execução; a primeira
publicação pode ser uma fotografia importada do snapshot processado.

## Objetivo e público

O dashboard atende o comprador responsável por uma categoria. A página inicial
deve responder, antes de qualquer exploração: qual é a exposição da categoria,
quais contratos exigem decisão, como o gasto evolui e quais fornecedores
merecem atenção financeira, de risco ou homologação.

Fornecedor é uma entidade legal (CNPJ). A visão por grupo econômico é um corte
de análise, sem somar indicadores financeiros de matriz e filial.

## Atualização e contrato de consumo

O fluxo de atualização é:

```text
generate_raw ou update_raw → run_etl → build_analytics → Atualizar no Power BI
```

No Windows, configure o DuckDB ODBC Driver e uma conexão para o arquivo
`contract_analytics.duckdb`. No Power BI, mantenha o parâmetro
`AnalyticsDatabasePath` documentado junto à conexão para apontar ao banco da
execução analítica desejada.

Importar apenas as estruturas abaixo. As views `src_*`, Parquets das camadas
RAW/STAGING/CURATED e consultas ad hoc não fazem parte do contrato do
dashboard.

| Estrutura | Uso no Power BI |
|---|---|
| `analytics_run_context` | Exibir `pipeline_run_id`, cenário e data de referência do snapshot. |
| `vw_suppliers` | Base da dimensão compartilhada de fornecedor. |
| `vw_contracts` | Carteira, saldo, consumo, status e vigência. |
| `vw_spending` | Pagamentos, tendências e concentração. |
| `vw_renewals` | Renovações, aportes e linha do tempo de aditamentos. |
| `vw_rfi` | Homologação e risco mais recente. |
| `vw_supplier_financials` | Receita, custos, lucros e dependência financeira anual. |
| `vw_quality_reconciliation` | Status, match rate e deltas do quality gate. |
| `vw_quality_exceptions` | Detalhe de exceções publicadas. |

## Modelo semântico no Power BI

- Criar `dSupplier` a partir de `vw_suppliers` e relacioná-la por `supplier_key`
  às views de contratos, spending, renovações, RFI e financeiro.
- Tratar `vw_contracts` como `dContract` no modelo de consumo, pois seu grão é
  um contrato; relacioná-la por `contract_key` a pagamentos e aditamentos.
- Criar `dCategory` a partir dos valores distintos de `category_key`, código,
  nome, macrogrupo, grupo e família de `vw_contracts`; relacioná-la às views
  contratuais por `category_key`.
- Manter a hierarquia de filtro:
  `category_macro_group → category_group → category_family → category_name`.
- Usar calendário local do Power BI somente para controlar eixos e seletores de
  data. Regras de valor, saldo, risco e dependência permanecem no DuckDB/SQL.
- Não criar relacionamento entre fatos. A agregação usa dimensões compartilhadas
  ou cada visual consulta sua view no próprio grão.

`Escopo` neste dashboard significa a hierarquia de categoria. O nome do contrato
é exibido como detalhe, mas não é uma dimensão formal de escopo.

## Filtros e navegação

Filtros de destaque na página inicial:

- hierarquia de categoria;
- fornecedor ou grupo econômico;
- período, quando o visual possuir data.

As páginas de detalhe expõem filtros adicionais conforme o domínio: status
contratual, tipo de contrato, tipo de aditamento, centro de custo, homologação,
risco e ano financeiro.

O menu principal terá as páginas **Visão da Categoria**, **Contratos e
Renovações**, **Spending**, **Fornecedores e Risco** e **Qualidade**. O
drill-through por `supplier_key` leva qualquer fornecedor à página de
Fornecedores e Risco. A página inicial também terá links para detalhes de
contratos com vencimento e exceções de qualidade.

## Páginas e visuais

### Visão da Categoria

| Visual | Métrica e fonte | Critério de validação |
|---|---|---|
| Cards de carteira | Valor contratado, saldo e consumo de `01_contract_balance_and_consumption.sql`. | Totais reconciliam com `vw_contracts` no mesmo filtro de categoria. |
| Card de spending | `SUM(payment_value)` em `vw_spending`. | Reconciliar com o total de `03_spending_concentration.sql`. |
| Card de ação | Contratos vencidos ou dentro de 90 dias de `02_contract_expiry.sql`. | Contagem igual à consulta SQL na data de referência exibida. |
| Principais contratos | Contratos por valor total/saldo de `vw_contracts`, com marcadores de renovação e aporte de `vw_renewals`. | Cada marcador corresponde a pelo menos um aditamento do tipo indicado para o mesmo `contract_key`. |
| Valor por escopo | Coluna por macrogrupo, grupo, família ou categoria usando `vw_contracts` e `vw_spending`. | A soma das categorias selecionadas equivale ao card correspondente. |
| Tendência de spending | Linha mensal de `vw_spending`. | Soma dos meses equivale ao spending total do filtro. |
| Principais fornecedores | Ranking de gastos de `03_spending_concentration.sql`, enriquecido com risco e dependência das views de RFI e financeira. | Ranking e participação iguais à consulta KPI sob o mesmo filtro. |

### Contratos e Renovações

| Visual | Métrica e fonte | Critério de validação |
|---|---|---|
| Consumo e saldo | `01_contract_balance_and_consumption.sql`. | Percentual de consumo é nulo sem valor contratado e reconcilia por fornecedor/categoria. |
| Vencimentos | Faixas de `02_contract_expiry.sql`. | A classificação usa `as_of_date` de `analytics_run_context`. |
| Linha do tempo | Eventos de `vw_renewals` por vigência e tipo. | Cada evento corresponde a um `amendment_id` único. |
| Tabela operacional | Contrato, fornecedor, categoria, saldo, risco, vigência e flags de renovação/aporte. | Sem duplicar contrato ao relacionar eventos; eventos são agregados por `contract_key`. |

### Spending

| Visual | Métrica e fonte | Critério de validação |
|---|---|---|
| Tendência mensal | `SUM(payment_value)` por mês em `vw_spending`. | Soma mensal igual ao total filtrado. |
| Mix por escopo | Spending por hierarquia de `dCategory`. | A soma das partes equivale ao spending total. |
| Concentração | Ranking e participação de `03_spending_concentration.sql`. | Participações somam 100% para o filtro aplicado. |
| Detalhe de pagamentos | Eventos de `vw_spending`. | Cada linha representa um `payment_id`. |

### Fornecedores e Risco

| Visual | Métrica e fonte | Critério de validação |
|---|---|---|
| Homologação e risco | Avaliação mais recente de `04_supplier_homologation_risk.sql`. | Uma linha por fornecedor após o ranking da avaliação. |
| Dependência financeira | Ranking de `05_supplier_financial_dependency.sql`. | Razões correspondem a `vw_supplier_financials`; denominador zero gera nulo. |
| Perfil financeiro | Coluna empilhada de `total_cost + gross_profit`, linha de `net_income` e referência de faturamento. | Custo mais lucro bruto recompõe o faturamento em cada fornecedor-ano. |
| Perfil do fornecedor | Identificação, grupo econômico, risco, gastos e contratos por `supplier_key`. | Não somar indicadores financeiros de matriz e filial. |

### Qualidade

| Visual | Métrica e fonte | Critério de validação |
|---|---|---|
| Cards de qualidade | Status, match rate e delta de `vw_quality_reconciliation`. | Iguais ao relatório curated do mesmo `pipeline_run_id`. |
| Exceções por entidade | Contagem de `vw_quality_exceptions`. | Detalhe preserva a contagem do card. |
| Tabela de investigação | Chave de negócio, causa, entidade e linhagem de `vw_quality_exceptions`. | Cada linha corresponde a uma exceção publicada; nenhuma é descartada. |

## Alertas e padrões visuais

- Destaque para contratos vencidos e a vencer em 30, 60 e 90 dias.
- Destaque para homologação não ativa e risco final alto.
- Dependência financeira é apresentada como razão contínua; não haverá faixas
  de severidade sem regra de negócio aprovada.
- Erros ou exceções de qualidade são visíveis na página inicial e levam à página
  de Qualidade.
- Não empilhar faturamento, custo e lucro juntos: faturamento já contém os
  componentes. O visual financeiro empilha custo e lucro bruto.

## Checklist de aceitação para a construção do `.pbix`

1. A conexão ODBC aponta para um banco DuckDB criado por manifesto aprovado.
2. O contexto da execução está visível no relatório.
3. Nenhum visual consulta RAW, STAGING, Parquet ou `src_*`.
4. Cada visual desta especificação reconcilia com seu KPI SQL ou view de origem.
5. Filtros de categoria, fornecedor e período atualizam somente os visuais cujo
   grão é compatível.
6. Não há relacionamento fato-com-fato, dupla contagem de aditamentos ou soma
   financeira indevida entre matriz e filial.
7. Navegação, drill-through, títulos, unidades monetárias e estados de alerta
   funcionam em resolução de notebook.

## Fora do escopo desta issue

- Construção e versionamento do arquivo `.pbix`.
- Publicação no Power BI Service, criação de embed público e licenciamento.
- Gateway e atualização agendada.
- Novas métricas, novos dados de escopo ou alterações adicionais no ETL.
