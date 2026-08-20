# Validação do dashboard

Execute este checklist depois de atualizar o Power BI. A fonte de comparação é
o mesmo arquivo DuckDB selecionado no DSN `Contract_analytics`.

## Modelo e navegação

- [ ] O cabeçalho mostra `pipeline_run_id`, cenário e `as_of_date` de
  `analytics_run_context`.
- [ ] Nenhuma consulta importa `src_*`, arquivos Parquet ou dados de RAW,
  STAGING e CURATED.
- [ ] `dSupplier` e `dCategory` são dimensões distintas derivadas das views
  autorizadas; não existe relacionamento fato-a-fato.
- [ ] A hierarquia `macrogrupo > grupo > família > categoria` está disponível
  em filtros e drill-down.
- [ ] O drill-through por `supplier_key` chega a **Fornecedores e Risco**.
- [ ] As cinco páginas existem: Visão da Categoria, Contratos e Renovações,
  Spending, Fornecedores e Risco e Qualidade.

## Reconciliação de KPIs

Sob o mesmo filtro de categoria, fornecedor e período aplicado no relatório:

- [ ] Valor contratado, saldo e consumo igualam
  `2.scr/4.analytics/kpis/01_contract_balance_and_consumption.sql`.
- [ ] Vencidos, até 30 e até 90 dias respeitam a data de referência e igualam
  `02_contract_expiry.sql`.
- [ ] Spending total, ranking e participação por fornecedor igualam
  `03_spending_concentration.sql`.
- [ ] Homologação e riscos usam somente a avaliação mais recente por fornecedor,
  conforme `04_supplier_homologation_risk.sql`.
- [ ] Receita, custo, lucro e dependência financeira igualam
  `05_supplier_financial_dependency.sql`. O gráfico empilha apenas custo e
  lucro bruto; faturamento é a referência, não uma terceira coluna empilhada.
- [ ] Cards e tabela de qualidade igualam `06_data_quality.sql`.

## Verificação visual

- [ ] Moeda exibida como R$; percentuais com denominador explícito e valores
  nulos preservados quando não há denominador.
- [ ] Cards de alerta destacam contratos vencidos e a vencer; não atribuem
  severidade nova à dependência financeira.
- [ ] Tabela de contratos não duplica linhas quando exibe renovação ou aporte.
- [ ] Tendência mensal soma exatamente o Spending Total filtrado.
- [ ] Visuais, tooltips, filtros e navegação funcionam na resolução de notebook.
