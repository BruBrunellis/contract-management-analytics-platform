# Validação do dashboard

Execute este checklist depois de atualizar o Power BI. A fonte de comparação é
o mesmo arquivo DuckDB selecionado no DSN `Contract_analytics`.

## Modelo e navegação

- [ ] O cabeçalho mostra `pipeline_run_id`, cenário e `as_of_date` de
  `analytics_run_context`.
- [ ] O segmentador de posição acumulada usa `dCalendar[Date]`; o segmentador
  anual usa `dAno[Ano]` e não possui relacionamento com as tabelas do modelo.
- [ ] Nenhuma consulta importa `src_*`, arquivos Parquet ou dados de RAW,
  STAGING e CURATED.
- [ ] `dSupplier` e `dCategory` são dimensões distintas derivadas das views
  autorizadas; não existe relacionamento fato-a-fato.
- [ ] A hierarquia `macrogrupo > grupo > família > categoria` está disponível
  em filtros e drill-down.
- [ ] O drill-through por `supplier_key` chega a **Fornecedores e Risco**.
- [ ] As quatro páginas existem: Visão de Categoria, Painel de Contratos,
  Painel de Spending e Painel de Fornecedores.

## Reconciliação de KPIs

Sob o mesmo filtro de categoria, fornecedor e período aplicado no relatório:

- [ ] Valor contratado, saldo e consumo igualam
  `2.src/4.analytics/kpis/01_contract_balance_and_consumption.sql`.
- [ ] Na posição acumulada, o contratado é `original_value` mais renovações e
  aportes com início até a data de corte; o consumido é a soma de pagamentos
  até a mesma data.
- [ ] Na visão anual, contratado, consumido e aportes incluem apenas eventos do
  ano selecionado; `Saldo em 31 de Dezembro` é a posição acumulada de
  fechamento, não o fluxo líquido anual.
- [ ] `Contratos Encerrados` conta contratos com status `encerrado` cuja
  `risk_evaluation_date` esteja dentro do ano de `dAno`; a métrica é 5 para
  2025 no snapshot `20260820_214241` sem filtros de categoria.
- [ ] No **Painel de Contratos**, o risco final ponderado usa `balance_value`
  como peso e os pesos alto = 100%, médio = 50% e baixo = 10%. Sem filtros, o
  valor esperado para o snapshot `20260820_214241` é aproximadamente 42,9%.
- [ ] O tracking de consumo mostra somente contratos ativos e calcula risco de
  aporte pela diferença entre consumo e vigência decorrida, usando a
  `as_of_date` do snapshot como referência.
- [ ] O grid de variação por categoria compara a janela selecionada de 6, 12,
  24, 36 ou 48 meses com a janela anterior de igual duração. Alterar `dAno`
  não modifica esse grid; alterar `dJanelaComparacao[Meses]` não modifica os
  demais visuais do Painel de Contratos.
- [ ] Vencidos, até 30 e até 90 dias respeitam a data de referência e igualam
  `02_contract_expiry.sql`.
- [ ] Spending total, ranking e participação por fornecedor igualam
  `03_spending_concentration.sql`.
- [ ] Na página **Painel de Spending**, nenhum ano selecionado mostra o
  histórico completo; ao selecionar um botão de `dCalendar[Ano]`, o card, os
  gráficos trimestral e por categoria, e a tabela exibem somente pagamentos
  daquele ano.
- [ ] Homologação e riscos usam somente a avaliação mais recente por fornecedor,
  conforme `04_supplier_homologation_risk.sql`.
- [ ] A tabela do Painel de Fornecedores apresenta somente fornecedores com ao
  menos um contrato ativo na `as_of_date`. Para cada fornecedor, o valor ativo
  anualizado é `SUM(total_value × 365,25 / duração_em_dias)` nessa população e
  a dependência usa o faturamento de maior `financial_period_end_date`.
- [ ] A dependência por categoria é a média ponderada no grão de contrato:
  `SUM(dependência × valor anualizado) / SUM(valor anualizado)`. Não pode ser
  média simples de fornecedores ou de cartões de categoria.
- [ ] Os cards de cenários contam fornecedores distintos por
  `financial_scenario`, restritos à população com contrato ativo. A soma dos
  cenários deve igualar a contagem distinta de fornecedores ativos quando não
  houver filtro de cenário.
- [ ] O gráfico de saúde financeira usa `financial_year`: colunas de
  faturamento bruto e custo total e linha de margem líquida ponderada
  (`SUM(net_income) / SUM(gross_revenue)`) para fornecedores ativos. Cada ano
  deve poder variar; não reutilizar o mesmo total em todos os pontos do eixo.
- [ ] Cards e tabela de qualidade igualam `06_data_quality.sql`.

## Verificação visual

- [ ] Moeda exibida como R$; percentuais com denominador explícito e valores
  nulos preservados quando não há denominador.
- [ ] Cards de alerta destacam contratos vencidos e a vencer; não atribuem
  severidade nova à dependência financeira.
- [ ] Tabela de contratos não duplica linhas quando exibe renovação ou aporte.
- [ ] Tendência mensal soma exatamente o Spending Total filtrado.
- [ ] Visuais, tooltips, filtros e navegação funcionam na resolução de notebook.
