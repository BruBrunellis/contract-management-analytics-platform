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
  entre snapshots diferentes. A análise histórica do dashboard é reconstruída
  dentro de um único snapshot a partir das datas de início de contratos e
  aditamentos e das datas de pagamento.
- Fornecedor significa entidade legal (CNPJ). Métricas financeiras não somam
  automaticamente matriz e filiais, porque os valores da fonte não são
  aditivos no nível de CNPJ8.

## Contratos e consumo

Além dos KPIs de snapshot, o dashboard disponibiliza duas leituras temporais
em DAX. A **posição acumulada** usa uma data de corte: valor contratado é o
valor original dos contratos iniciados até a data mais as renovações e aportes
efetivos até ela; valor consumido é o pagamento acumulado; saldo é contratado
menos consumido. A **visão anual** mostra somente os eventos e pagamentos do
ano selecionado. Seu `Saldo em 31 de Dezembro` continua sendo a posição
acumulada de fechamento; `Variação Líquida no Ano` é a diferença entre os
fluxos do ano.

| KPI | Fórmula e grão | Fonte e tratamento |
|---|---|---|
| Valor contratado do snapshot | `SUM(total_value)` por fornecedor e macrogrupo de categoria. | `vw_contracts`; contratos não resolvidos ficam fora da métrica e aparecem nas exceções. |
| Saldo contratual do snapshot | `SUM(balance_value)` no mesmo grão. | `vw_contracts`; não é recalculado a partir de pagamentos. |
| Valor consumido do snapshot | `SUM(total_value - balance_value)`. | `vw_contracts`; preserva a regra de negócio consolidada no curated. |
| Percentual de consumo | `valor consumido / valor contratado`. | Retorna nulo quando não houver valor contratado. |

Consulta: `01_contract_balance_and_consumption.sql`. As medidas temporais do
dashboard estão em `3.dashboard/measures/dashboard_measures.dax` e usam
`validity_start_date` como data efetiva dos eventos de contrato e aditamento.

## Vencimento e renovação

| KPI | Fórmula e grão | Fonte e tratamento |
|---|---|---|
| Dias até vencimento | `validity_end_date - as_of_date` por contrato. | `vw_contracts` e `analytics_run_context`. |
| Encerramentos no ano | Contagem distinta de contratos com status `encerrado` e `risk_evaluation_date` dentro do ano selecionado. | `vw_contracts`; no cenário atual, a avaliação de risco registrada é a data do encerramento. |
| Risco final ponderado | Média ponderada pelo `balance_value`: alto = 100%, médio = 50% e baixo = 10%. | `vw_contracts`; o saldo representa a exposição ainda aberta, por isso é preferível a `total_value`. |
| Risco de aporte | Diferença entre percentual consumido e percentual de vigência decorrida: alto a partir de +20 p.p.; médio a partir de +5 p.p.; baixo abaixo disso. | `vw_contracts` e `analytics_run_context[as_of_date]`; exibido somente para contratos ativos. |
| Variação contratada por categoria | `(valor da janela atual - valor da janela anterior) / valor da janela anterior`. | Janelas de 6, 12, 24, 36 ou 48 meses, encerradas na `as_of_date`; cada uma contém contratos iniciados e aditamentos iniciados no intervalo. Retorna nulo sem base anterior positiva. |
| Faixa de vencimento | Vencido, até 30, 60, 90 dias ou fora da janela. | A data de referência é a do manifesto, não a data do computador. |

Consulta: `02_contract_expiry.sql`. Os KPIs de snapshot não somam eventos de
`vw_renewals` a `total_value`, para evitar dupla contagem. Já as medidas
temporais partem exclusivamente de `original_value` e adicionam cada evento
efetivo até a data de corte, sem usar `total_value` nesse cálculo.

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
| Valor anualizado de contratos ativos | Soma de `total_value / duração_em_dias × 365,25` dos contratos com status ativo, início até e término a partir da `as_of_date`. | `vw_contracts`; a população é a carteira sendo consumida na data do snapshot, não os contratos que apenas se sobrepõem a um ano fiscal. |
| Dependência financeira | `valor anualizado de contratos ativos / faturamento bruto mais recente` por fornecedor. | O faturamento mais recente é identificado por `financial_period_end_date`; denominador zero ou ausente retorna nulo. |
| Dependência financeira ponderada por categoria | `SUM(dependência do fornecedor × valor anualizado do contrato) / SUM(valor anualizado do contrato)`. | Calculada no grão de contrato ativo; exclui contratos sem dependência válida e evita média simples de fornecedores. |
| Valor contratado nos últimos 12 meses | Valor original de contratos e valor de aditamentos iniciados entre `EDATE(as_of_date, -12) + 1` e `as_of_date`. | `vw_contracts` e `vw_renewals`; usado como métrica de exposição recente, não como saldo. |
| Cenários financeiros — fornecedores ativos | Contagem distinta de fornecedores por `financial_scenario`. | Inclui somente fornecedores com ao menos um contrato ativo na `as_of_date`. |
| Cobertura de faturamento | `faturamento bruto mais recente / valor anualizado de contratos ativos`. | Retorna nulo sem contratos anualizados ou faturamento disponível. |

Consulta: `05_supplier_financial_dependency.sql`.

No gráfico de saúde financeira, use `financial_year` no eixo, colunas lado a
lado de faturamento bruto e custo total e uma linha em eixo secundário para a
margem líquida ponderada (`SUM(net_income) / SUM(gross_revenue)`). A população
permanece restrita aos fornecedores ativos na `as_of_date`; os valores
financeiros são exibidos no respectivo ano financeiro.

## Qualidade

| KPI | Fórmula e grão | Fonte e tratamento |
|---|---|---|
| Match rate | Registros publicados / registros de origem por entidade. | `vw_quality_reconciliation`. |
| Delta de reconciliação | Diferença de contagem ou de valor monetário entre fonte, fato e exceções. | Valores diferentes de zero requerem investigação. |
| Exceções | Contagem de registros explicitamente isolados por entidade. | `vw_quality_exceptions`; não é descartada silenciosamente. |

Consulta: `06_data_quality.sql`.
