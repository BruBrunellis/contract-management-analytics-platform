# Dicionário de métricas e KPIs

As consultas em `2.scr/4.analytics/kpis/` são a implementação versionada dos
KPIs. Elas devem ser executadas no banco DuckDB construído a partir de um
`etl_manifest.json` com quality gate aprovado.

## Convenções gerais

- As métricas consomem somente views analíticas, que leem os Parquets curated
  declarados no manifesto da execução.
- Registros em arquivos de exceção não são incluídos nos numeradores nem nos
  denominadores. A consulta `06_data_quality.sql` torna essa exclusão visível.
- Valores monetários representam o snapshot processado; não devem ser somados
  entre snapshots diferentes.
- Fornecedor significa entidade legal (CNPJ). Métricas financeiras não somam
  automaticamente matriz e filiais, porque os valores da fonte não são
  aditivos no nível de CNPJ8.

## Contratos e consumo

| KPI | Fórmula e grão | Fonte e tratamento |
|---|---|---|
| Valor contratado | `SUM(total_value)` por fornecedor e macrogrupo de categoria. | `vw_contracts`; contratos não resolvidos ficam fora da métrica e aparecem nas exceções. |
| Saldo contratual | `SUM(balance_value)` no mesmo grão. | `vw_contracts`; não é recalculado a partir de pagamentos. |
| Valor consumido | `SUM(total_value - balance_value)`. | `vw_contracts`; preserva a regra de negócio consolidada no curated. |
| Percentual de consumo | `valor consumido / valor contratado`. | Retorna nulo quando não houver valor contratado. |

Consulta: `01_contract_balance_and_consumption.sql`.

## Vencimento e renovação

| KPI | Fórmula e grão | Fonte e tratamento |
|---|---|---|
| Dias até vencimento | `validity_end_date - as_of_date` por contrato. | `vw_contracts` e `analytics_run_context`. |
| Faixa de vencimento | Vencido, até 30, 60, 90 dias ou fora da janela. | A data de referência é a do manifesto, não a data do computador. |

Consulta: `02_contract_expiry.sql`. Eventos de renovação permanecem consultáveis
em `vw_renewals`, sem serem somados ao valor do contrato para evitar dupla
contagem.

## Spending e concentração

| KPI | Fórmula e grão | Fonte e tratamento |
|---|---|---|
| Gasto total | `SUM(payment_value)` por grupo econômico e fornecedor. | `vw_spending`; somente pagamentos com chaves resolvedas. |
| Concentração de gasto | `gasto do fornecedor / gasto total da carteira`. | Retorna nulo se a carteira não possuir gasto. |
| Ranking de gasto | `DENSE_RANK` por gasto total decrescente. | Empates recebem a mesma posição. |

Consulta: `03_spending_concentration.sql`.

## Homologação e risco

| KPI | Fórmula e grão | Fonte e tratamento |
|---|---|---|
| Situação de homologação | Resultado e status da avaliação mais recente por fornecedor. | `vw_rfi`; ordenação por data de avaliação e ID do evento. |
| Risco do fornecedor | Risco financeiro, trabalhista e final da mesma avaliação. | Não agrega fatos de risco com gastos ou contratos. |

Consulta: `04_supplier_homologation_risk.sql`.

## Financeiro de fornecedores

`fact_supplier_financial` possui o grão fornecedor legal × ano fiscal. A fonte
é `stg_empresas`: faturamento, custo, custo de folha, lucro bruto, juros da
dívida e lucro líquido de 2022 a 2026. O `fact_rfi` continua reservado aos
eventos de homologação e risco; ele não é uma tabela de respostas financeiras.

| KPI | Fórmula e grão | Fonte e tratamento |
|---|---|---|
| Faturamento bruto anual | `gross_revenue` por fornecedor e ano fiscal. | `vw_supplier_financials`; receita zero produz razão de dependência nula. |
| Valor anualizado de contratos | Soma de `total_value / duração_em_dias × 365,25` dos contratos vigentes em algum momento do ano fiscal. | Contratos sobrepostos ao período fiscal; não soma pagamentos nem aditamentos. |
| Dependência financeira | `valor anualizado dos contratos / faturamento bruto anual`. | Quanto maior a razão, maior a exposição do fornecedor ao comprador. |
| Cobertura de faturamento | `faturamento bruto anual / valor anualizado dos contratos`. | Corresponde à fórmula solicitada; retorna nulo sem contratos anualizados. |

Consulta: `05_supplier_financial_dependency.sql`.

Para visualização, use coluna empilhada de `total_cost + gross_profit`, que
recompõe o faturamento, e linha de `net_income`. Não empilhe faturamento, custo
e lucro na mesma coluna: faturamento já contém os outros componentes.

## Qualidade

| KPI | Fórmula e grão | Fonte e tratamento |
|---|---|---|
| Match rate | Registros publicados / registros de origem por entidade. | `vw_quality_reconciliation`. |
| Delta de reconciliação | Diferença de contagem ou de valor monetário entre fonte, fato e exceções. | Valores diferentes de zero requerem investigação. |
| Exceções | Contagem de registros explicitamente isolados por entidade. | `vw_quality_exceptions`; não é descartada silenciosamente. |

Consulta: `06_data_quality.sql`.
