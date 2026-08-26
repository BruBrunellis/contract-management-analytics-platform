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
  data. A `dCalendar` filtra pagamentos e determina a data de corte dos cards
  acumulados. A `dAno` é uma dimensão desconectada usada exclusivamente nos
  cards anuais, para que a comparação de fluxo anual não altere a posição
  acumulada selecionada no calendário.
- Não criar relacionamento entre fatos. A agregação usa dimensões compartilhadas
  ou cada visual consulta sua view no próprio grão.

### Perspectivas temporais dos cards

- **Posição acumulada:** o segmentador `dCalendar[Date]` determina a data de
  corte. Valor contratado reúne o valor original dos contratos e os
  aditamentos com início até a data; valor consumido reúne pagamentos até a
  mesma data; saldo é a diferença entre ambos.
- **Visão do ano:** o segmentador desconectado `dAno[Ano]` apresenta somente os
  contratos iniciados, renovações, aportes e pagamentos ocorridos no ano.
  `Saldo em 31 de Dezembro` continua sendo uma posição acumulada até o último
  dia do ano, e não a diferença dos fluxos daquele ano. A medida opcional
  `Variação Líquida no Ano` expressa essa diferença de fluxos.
- **Encerramentos no ano:** contratos encerrados são datados por
  `vw_contracts[risk_evaluation_date]`, pois o cenário atual encerra contratos
  a partir da avaliação de risco. A métrica não usa a vigência final planejada.
- `analytics_run_context[as_of_date]` identifica a data do snapshot carregado;
  não é o seletor da análise histórica.
- **Comparação móvel por categoria:** a tabela desconectada
  `dJanelaComparacao[Meses]` oferece 6, 12, 24, 36 e 48 meses. Ela compara a
  janela encerrada na `as_of_date` com a janela imediatamente anterior de igual
  duração, considerando valores originais, renovações e aportes. Sua interação
  deve ser limitada ao grid de variação por categoria; `dAno` continua sendo o
  seletor do restante do painel.

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

O menu principal terá as páginas **Visão de Categoria**, **Painel de
Contratos**, **Painel de Spending** e **Painel de Fornecedores**. A página de
fornecedores concentra a consulta operacional por CNPJ, sem drill-through
obrigatório. Exceções de qualidade permanecem disponíveis nas views de
qualidade e no checklist de validação.

## Páginas e visuais

### Visão da Categoria

| Visual | Métrica e fonte | Critério de validação |
|---|---|---|
| Cards de carteira | Posição contratada, consumo acumulado e saldo na data de corte. | O contratado soma valores originais e eventos com início até o corte; o saldo é contratado menos pagamentos acumulados. |
| Cards de visão anual | Contratado no ano, consumido no ano, saldo em 31 de dezembro e aportes no ano. | O filtro `dAno` não interfere na posição acumulada; o saldo anual é uma posição de fechamento. |
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

### Painel de Contratos

| Visual | Métrica e fonte | Critério de validação |
|---|---|---|
| Contratos de risco alto | Detalhe de `vw_contracts` com `final_risk = alto`. | Cada linha possui risco alto e respeita os filtros de categoria e status. |
| Vencimento próximo | Contratos ativos com vencimento entre a data de referência do snapshot e os 90 dias seguintes. | Igual ao critério de `02_contract_expiry.sql`. |
| Concentração de risco | Risco final ponderado pelo saldo: alto = 100%, médio = 50%, baixo = 10%. | Denominador é a soma de `balance_value` positivo no filtro aplicado. |
| Variação por categoria | Variação do valor contratado entre a janela móvel selecionada e a janela anterior de mesma duração. | Usa `dJanelaComparacao` (6, 12, 24, 36 ou 48 meses), com fim na `as_of_date`; não é afetada por `dAno`. |
| Tracking de consumo | Percentual consumido, vigência decorrida e risco de aporte para contratos ativos. | Alto quando o consumo supera a vigência decorrida em 20 p.p.; médio a partir de 5 p.p. |

### Spending

| Visual | Métrica e fonte | Critério de validação |
|---|---|---|
| Botões de ano | Segmentador `dCalendar[Ano]` em modo Tile. Sem seleção, mostra todo o histórico; um ano selecionado filtra todos os visuais da página. | O total sem seleção é igual ao histórico completo; cada botão reconcilia com os pagamentos do respectivo ano. |
| Card de spending selecionado | `SUM(payment_value)` em `vw_spending`. | Igual à soma dos pagamentos no contexto de ano aplicado. |
| Tendência trimestral | `SUM(payment_value)` por `dCalendar[Ano-Trimestre]`. | Soma dos trimestres igual ao total filtrado. |
| Mix por categoria | Spending por `vw_spending[category_name]`. | A soma das partes equivale ao spending total. |
| Detalhe de pagamentos | Eventos de `vw_spending`. | Cada linha representa um `payment_id`. |

### Fornecedores e Risco

| Visual | Métrica e fonte | Critério de validação |
|---|---|---|
| Tabela de dependência | CNPJ, fornecedor, valor anualizado de contratos ativos, dependência financeira, último faturamento, homologação e risco final. | Uma linha por fornecedor com ao menos um contrato ativo na `as_of_date`; homologação e risco vêm da avaliação mais recente. |
| Dependência por categoria | Média ponderada da dependência dos contratos ativos, usando o valor anualizado de cada contrato como peso. | Numerador é `dependência do fornecedor × valor anualizado`; denominador é a soma dos valores anualizados válidos. |
| Cenários financeiros | Contagem distinta de fornecedores por `financial_scenario`. | Conta apenas fornecedores que tenham contrato ativo na `as_of_date`, respeitando os filtros de categoria. |
| Saúde financeira histórica | Colunas de faturamento bruto e custo total, com linha de margem líquida ponderada. | O eixo é `financial_year`; a margem é `SUM(net_income) / SUM(gross_revenue)` da população de fornecedores ativos. |
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

## Checklist de aceitação para a construção do projeto Power BI

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

## Fora do escopo do dashboard MVP

- Publicação no Power BI Service, criação de embed público e licenciamento.
- Gateway e atualização agendada.
- Novas métricas, novos dados de escopo ou alterações adicionais no ETL.

As consultas, medidas, instruções de atualização e checklist de validação que
materializam esta especificação estão em [`3.dashboard`](../3.dashboard/README.md).
