# Inventário SQL/DAX e baseline de métricas

Referência para a [issue #55](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/55) e para a consolidação SQL da [#56](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/56). A leitura estática usa o modelo e o relatório PBIP versionados na base `adba6c0`.

## Fontes e filtros do modelo vigente

- As partições M importam as views públicas e `analytics_run_context` do schema `main` de `contract_analytics` pelo DSN `Contract_analytics`. `dSupplier` vem de `vw_suppliers`. `dCategory` projeta a hierarquia a partir de `vw_contracts` e retém uma linha por `category_key`. Consulte as [partições do TMDL](../3.dashboard/contract_management_analytics.SemanticModel/definition/tables) e os [contratos das views](analytics_contracts.md).
- Fornecedor e categoria filtram contratos pelas chaves das dimensões. Pagamentos e aditamentos também recebem esses filtros via `contract_key`. Seus relacionamentos diretos com fornecedor e categoria estão inativos. Fornecedor também filtra RFI e financeiro diretamente. Categoria não filtra a tabela financeira diretamente. A população contratual define quando categoria afeta a seleção de fornecedores.
- `dCalendar` abrange da menor à maior data entre início de contrato, início de aditamento e data de pagamento. Sua relação com fatos é por `vw_spending.payment_date`. Os calendários locais automáticos têm papéis próprios. `dAno`, `dJanelaComparacao` e `Top N Fornecedores` são desconectadas. O modelo deriva os anos de `dCalendar`, oferece janelas de 6, 12, 24, 36 e 48 meses e oferece Top N de 5, 10, 15 e 20. O contexto da execução se relaciona à reconciliação por `pipeline_run_id`. Consulte os [relacionamentos](../3.dashboard/contract_management_analytics.SemanticModel/definition/relationships.tmdl).

As 65 declarações do modelo estão nas tabelas abaixo. A inspeção das referências `Measure` na [definição do relatório](../3.dashboard/contract_management_analytics.Report/definition), seguida das dependências entre medidas, encontrou 42 referências diretas distintas, 12 medidas alcançadas por dependência e 11 sem referência no PBIP versionado. Essa inspeção cobre consultas e filtros dos visuais e os demais JSON da definição do relatório. Ela registra a configuração salva do PBIP.

## Inventário das medidas TMDL

As linhas Lnn referenciam [analytics_run_context.tmdl](../3.dashboard/contract_management_analytics.SemanticModel/definition/tables/analytics_run_context.tmdl), com a outra tabela indicada na última linha. Categ, Contr, Spend e Forn indicam as quatro páginas. **Aux** indica uso indireto e **—** indica ausência de referência no relatório, inclusive por dependência.

**Negócio** preserva um cálculo ou parâmetro de negócio na baseline, inclusive quando a regra é compartilhada com outra medida. **Apresentação** identifica rótulos e filtros de exibição. **Descartar** indica que a migração dispensa uma medida dedicada. O TMDL é a referência para comportamento observado. As decisões de reconciliação estão na seção seguinte.

Os grãos de origem são contrato em `vw_contracts`, aditamento em `vw_renewals`, pagamento em `vw_spending`, avaliação em `vw_rfi` e CNPJ × exercício em `vw_supplier_financials`. As somas respeitam o contexto de fornecedor e categoria propagado pelo modelo, salvo as exceções indicadas. O padrão de exibição no TMDL é moeda com duas casas nas medidas monetárias formatadas, percentual com uma casa nas medidas percentuais formatadas e inteiro nas contagens e indicadores. **Geral** abaixo indica medida sem formato numérico explícito no TMDL. `SUM`, `SUMX` e `DISTINCTCOUNT` podem retornar `BLANK` em conjuntos vazios. Razões com `DIVIDE` retornam `BLANK` com denominador ausente ou zero, salvo indicação de fórmula diferente. Casos e contratos usam `NULL` para representar ausência e preservam a precisão durante cálculos e agregações.

### Posição e fluxo por exercício

| Medida | Linha | Uso | Destino | Cálculo, grão e filtros vigentes |
|---|---:|---|---|---|
| Spending Total | L4 | Spend | Negócio | Soma de `payment_value` por contexto de pagamentos, com `dCalendar` e demais filtros do visual. Moeda. |
| Data de Corte | L8 | Aux | Negócio | Máximo de `dCalendar.Date` no contexto da célula, incluindo eixo ou segmentador. Data. |
| Valor Original até o Corte | L14 | Aux | Negócio | Soma de `original_value` por contrato iniciado até o corte inclusivo, substituindo o filtro direto da data de início. Moeda. |
| Valor de Renovações até o Corte | L30 | Aux | Negócio | Soma de `amendment_value` por aditamento `renovacao` com início até o corte inclusivo. Moeda. |
| Valor de Aportes até o Corte | L45 | Categ | Negócio | Soma de `amendment_value` por aditamento `aporte` com início até o corte inclusivo. Moeda. |
| Valor Contratado até o Corte | L60 | Categ | Negócio | Soma dos três componentes contratados até o corte. Moeda. |
| Valor Consumido até o Corte | L68 | Categ | Negócio | Soma dos pagamentos até o corte inclusivo, substituindo todos os filtros de `dCalendar` pelo intervalo acumulado. Moeda. |
| Saldo Contratual no Corte | L79 | Categ | Negócio | Contratado menos consumido acumulados no mesmo contexto. Moeda. |
| Ano Selecionado | L85 | — | Negócio | Ano único de `dAno` ou máximo do ano em `dCalendar`. Parâmetro inteiro do fechamento. |
| Valor Original no Ano | L91 | Aux | Negócio | Soma do valor original dos contratos iniciados nos anos de `VALUES(dAno[Ano])`. Remove `dCalendar`. Moeda. |
| Valor de Renovações no Ano | L106 | Categ | Negócio | Soma dos aditamentos `renovacao` iniciados nos anos de `dAno`. Remove `dCalendar`. Moeda. |
| Valor de Aportes no Ano | L122 | Categ | Negócio | Soma dos aditamentos `aporte` iniciados nos anos de `dAno`. Remove `dCalendar`. Moeda. |
| Valor Contratado no Ano | L138 | Categ | Negócio | Soma do original, renovações e aportes dos exercícios selecionados. Moeda. |
| Valor Consumido no Ano | L146 | Categ | Negócio | Soma de pagamentos pela data de pagamento nos exercícios de `dAno`. Remove `dCalendar`. Moeda. |
| Valor Contratado até Fim do Ano | L161 | — | Negócio | Original e todos os aditamentos com início até 31/12 do ano resolvido, sem `dCalendar`. Moeda. |
| Valor Consumido até Fim do Ano | L178 | — | Negócio | Soma de pagamentos até 31/12 do ano resolvido, sem `dCalendar`. Moeda. |
| Saldo em 31 de Dezembro | L190 | — | Negócio | Contratado menos consumido, ambos acumulados até 31/12. O dicionário documenta a posição de fechamento. Moeda. |
| Variação Líquida no Ano | L196 | — | Negócio | Contratado menos consumido dentro dos exercícios de `dAno`. O dicionário documenta o fluxo líquido. Moeda. |
| Valor Renovado até Fim do Ano | L202 | — | Descartar | Soma de aditamentos `renovacao` até 31/12 sem `dCalendar`. O componente já é obtido com o corte e o tipo de evento. Moeda. |
| Valor Aportado até Fim do Ano | L219 | — | Descartar | Soma de aditamentos `aporte` até 31/12 sem `dCalendar`. O componente já é obtido com o corte e o tipo de evento. Moeda. |
| Ranking Fornecedor no Ano | L236 | Aux | Negócio | `RANKX` denso decrescente por contratado no ano entre razões sociais de `ALLSELECTED(dSupplier[supplier_legal_name])`. Inteiro. |
| Exibir Top Fornecedores no Ano | L248 | Categ (filtro) | Apresentação | Flag 1 para ranking até o N selecionado e `BLANK` para os demais. Filtro do visual de fornecedores. |
| Valor Consumido (Label bn) | L258 | Spend | Apresentação | Texto em bilhões de reais com duas casas a partir de `Valor Consumido no Ano`, propagando `BLANK`. A projeção Label pertence ao segmentador de `dCalendar.Ano`. |
| Top Fornecedores Value | L4 em [Top N Fornecedores.tmdl](../3.dashboard/contract_management_analytics.SemanticModel/definition/tables/Top%20N%20Fornecedores.tmdl) | Aux | Apresentação | Parâmetro inteiro do segmentador Top N. Seleção única ou 10 como padrão. |

### Contratos, risco e janelas

| Medida | Linha | Uso | Destino | Cálculo, grão e filtros vigentes |
|---|---:|---|---|---|
| Contratos Novos no Ano | L267 | Categ, Contr | Negócio | Contagem distinta de contratos `novo_contrato` iniciados em `dAno`, sem `dCalendar`. |
| Contratos Ativos | L283 | Categ, Contr | Negócio | Contagem distinta de `contract_key` com status `ativo` no snapshot. Substitui o filtro de status e remove `dCalendar`. |
| Contratos Vencidos | L294 | Categ, Contr | Negócio | Mesmo grão e filtros de Contratos Ativos, com status `vencido`. |
| Vencimento Próximo (90 dias) | L305 | Categ, Contr | Negócio | Contagem distinta de ativos com término entre `TODAY()` e `TODAY()+90`, inclusive. Substitui status, filtro direto de término e `dCalendar`. |
| Contratos Renovados no Ano | L323 | Categ, Contr | Negócio | Conta `contract_key` distintos dentre aditamentos `renovacao` iniciados em `dAno`, sem `dCalendar`. |
| Contratos Encerrados no Ano | L339 | Categ, Contr | Negócio | Conta contratos com status `encerrado` pela `risk_evaluation_date` do evento em `dAno`. Substitui status e remove `dCalendar`. |
| Contratos Vencidos no Ano | L356 | Categ, Contr | Negócio | Conta contratos com status `vencido` pela data de término em `dAno`. Substitui status e remove `dCalendar`. |
| Contratos Encerrados | L373 | Categ, Contr | Negócio | Contagem distinta com status `encerrado` no snapshot. Substitui status e remove `dCalendar`. |
| Risco Final Ponderado | L384 | Aux | Negócio | Em contratos com saldo positivo, soma de saldo × peso (alto 1, médio 0,5, baixo 0,1) dividida pela soma dos saldos positivos. Peso desconhecido fica em branco no numerador e o saldo segue no denominador. |
| Contratos com Risco Alto | L402 | Contr | Negócio | Contagem distinta de contratos por risco `alto`. Substitui o filtro direto de `final_risk`. |
| Contratos com Risco Médio | L411 | Contr | Negócio | Mesmo grão e contexto com risco `medio`. |
| Contratos com Risco Baixo | L420 | Contr | Negócio | Mesmo grão e contexto com risco `baixo`. |
| Maior Risco por Categoria | L429 | Contr | Negócio | Maior índice ponderado entre categorias de `ALLSELECTED`. Reaplica cada chave de categoria no cálculo. Percentual. |
| Categoria com Maior Risco | L454 | Contr | Negócio | Rótulo da categoria selecionada pelo maior índice e desempate pelo nome crescente via `TOPN`. |
| Categoria com Menor Risco | L481 | Contr | Negócio | Mesmo procedimento, com índice crescente. A expressão permite categorias cujo índice está em branco. Texto. |
| Exibir Contrato Ativo | L508 | — | Descartar | Flag 0/1 a partir do status no contexto da linha. O visual de tracking já usa filtro direto `contract_status = 'ativo'`. |
| Exibir Contrato de Risco Alto | L514 | Contr (filtro) | Apresentação | Flag 0/1 a partir de `MAX(final_risk)` na linha de contrato. |
| Exibir Contrato Próximo ao Vencimento | L520 | Contr (filtro) | Apresentação | Flag 0/1 para contrato ativo com término entre a Data de Referencia e 90 dias depois, inclusive. |
| Data de Referencia | L534 | Aux | Negócio | Máximo de `analytics_run_context.as_of_date`, com o grão da publicação. Data. |
| Percentual de Saldo por Contrato | L540 | Contr | Negócio | Soma de `balance_value` dividida pela soma de `total_value` no contexto de contrato. O visual filtra ativos. |
| Variação % Valor Contratado por Categoria | L549 | Contr | Negócio | (Atual − anterior) / anterior por contexto de categoria. TMDL retorna branco com base anterior vazia ou zero. |
| Menor Risco por Categoria | L562 | Contr | Negócio | Menor índice ponderado entre categorias de `ALLSELECTED`, reaplicando a chave por categoria. Percentual. |
| Risco de Aporte | L587 | Contr | Negócio | Em cada contrato, consumo relativo menos a fração decorrida da vigência limitada a 0–1 na `as_of_date`. Alto a partir de +20 p.p., médio a partir de +5 p.p., baixo abaixo disso. Branco se falta base de consumo ou vigência válida. O visual filtra ativos. |
| Janela Selecionada (Meses) | L627 | Aux | Negócio | Inteiro de `dJanelaComparacao` com seleção única ou 12 como padrão. |
| Valor Contratado — Período Atual | L633 | Aux | Negócio | Original e aditamentos iniciados entre `EDATE(as_of_date,-N)+1` e `as_of_date`, sem `dCalendar`. Moeda, formato Geral. |
| Valor Contratado — Período Anterior | L662 | Aux | Negócio | Mesma soma de `EDATE(as_of_date,-2N)+1` até `EDATE(as_of_date,-N)`, sem `dCalendar`. Moeda, formato Geral. |

### Carteira ativa e saúde financeira

| Medida | Linha | Uso | Destino | Cálculo, grão e filtros vigentes |
|---|---:|---|---|---|
| Valor Anualizado de Contratos Ativos | L692 | Aux | Negócio | Soma por contrato ativo e vigente na `as_of_date`. Anualiza `total_value` com 365,25 dividido pela duração inclusiva. Moeda, formato Geral. |
| Valor Anualizado Ativo — Fornecedor | L717 | Forn | Negócio | Resolve um fornecedor único pela dimensão ou pelo contrato. Remove filtros de contrato, categoria e fornecedor, e reaplica a chave resolvida à carteira ativa. Moeda, formato Geral. |
| Faturamento Mais Recente — Fornecedor | L736 | Forn | Negócio | No financeiro sem os filtros correntes, seleciona a maior data de fechamento publicada para o CNPJ resolvido e soma a receita nessa data. Moeda, formato Geral. |
| Dependência Financeira — Fornecedor | L764 | Forn | Negócio | Carteira ativa anualizada do CNPJ dividida pela receita mais recente do mesmo CNPJ. Percentual. |
| Dependência Financeira Ponderada por Categoria | L773 | Forn | Negócio | Média por contrato da seleção, ponderada pelo valor anualizado ativo positivo. Exclui contratos sem dependência válida. A razão de cada CNPJ usa sua carteira completa. Percentual. |
| Valor Contratado — Últimos 12M | L796 | — | Negócio | Soma de originais e aditamentos iniciados em janela móvel fixa de 12 meses até a `as_of_date`. A regra de janela é compartilhada. Moeda, formato Geral. |
| Status Homologação Atual | L826 | Forn | Negócio | Para o CNPJ da dimensão, maior texto de `homologation_status` na última `assessment_date`, ignorando outros filtros sobre `vw_rfi`. |
| Risco Final Atual | L846 | Forn | Negócio | Mesmo grão e data que o status, tomando o maior texto de `final_risk` de forma independente. |
| Valor Contratado 12M — Risco Alto | L866 | — | Negócio | Soma de contratado 12M para CNPJs cujo risco atual é alto, mantendo filtros do contexto contratual no valor. Moeda, formato Geral. |
| % Exposição em Risco Alto | L879 | — | Negócio | Contratado 12M de fornecedores de risco alto sobre contratado 12M da seleção. Razão, formato Geral. |
| Check Valor Ativo | L889 | Forn (filtro) | Apresentação | Flag 0/1 para carteira ativa anualizada do fornecedor maior que zero. |
| Cenários Financeiros | L901 | Forn | Negócio | Conta CNPJs distintos com ao menos um contrato ativo e vigente na `as_of_date`. Remove `dCalendar` e preserva o cenário de `dSupplier` e o contexto contratual. |
| Faturamento — Fornecedores Ativos | L923 | Forn | Negócio | Soma de `gross_revenue` no exercício financeiro do eixo para CNPJs com anualizado ativo positivo no contexto. Moeda, formato Geral. |
| Custo — Fornecedores Ativos | L936 | Forn | Negócio | Soma de `total_cost` com a mesma população e exercício do faturamento. Moeda, formato Geral. |
| Margem Líquida Ponderada — Fornecedores Ativos | L949 | Forn | Negócio | Soma de `net_income` dividida pela soma do faturamento nos mesmos fornecedores e exercício. Percentual. |

## Cobertura do SQL e do arquivo DAX de referência

| Consulta vigente | Grão e comportamento | Uso na reconciliação |
|---|---|---|
| `01_contract_balance_and_consumption.sql` | Razão social × macrogrupo. Conta contratos, soma `total_value` e `balance_value` e calcula consumo pela diferença. | Preservar o KPI de snapshot. As medidas temporais usam eventos de originais e aditamentos e pagamentos em datas próprias. |
| `02_contract_expiry.sql` | Contrato × data do snapshot. Diferença em dias e faixas 30/60/90, inclusive nos limites. O SQL não restringe status. | Manter faixa cronológica por contrato e contar o alerta de 90 dias na população ativa. Manter contagens por status como KPIs distintos. |
| `03_spending_concentration.sql` | Grupo econômico × razão social, com soma de pagamentos, participação no total da consulta e ranking denso por gasto. | Manter gasto, concentração e ranking de gasto. O Top N anual da Visão de Categoria usa valor contratado. Usar chaves de fornecedor para evitar fundir nomes iguais. |
| `04_supplier_homologation_risk.sql` | Uma avaliação por CNPJ, ordenada por data e `risk_assessment_id` decrescentes. | Usar status e riscos do mesmo registro. O DAX pode combinar textos de registros diferentes em empate de data. |
| `05_supplier_financial_dependency.sql` | Projeção do financeiro por CNPJ × exercício, com receita do exercício e contratos que interceptam o período. | Preservar a exposição e a razão anual. A dependência da carteira ativa tem outra população e outro denominador. |
| `06_data_quality.sql` | Reconciliação por entidade, com contagem de exceções pré-agregada e zero quando não há exceção correspondente. | Preservar taxa, deltas, status e exceções no grão de entidade da execução. O PBIP importa as views de qualidade. |

Fontes [consultas SQL de KPI](../2.src/4.analytics/kpis), [view de financeiro](../2.src/4.analytics/sql/08_vw_supplier_financials.sql) e [arquivo DAX de referência](../3.dashboard/measures/dashboard_measures.dax).

O arquivo DAX de referência tem 41 declarações, 30 com nome presente no TMDL e 11 presentes somente no arquivo auxiliar. Por exemplo, suas fórmulas anuais usam o ano escalar resolvido por `Ano Selecionado`, enquanto os fluxos em TMDL usam o conjunto de anos. `Contratos Vencidos` no auxiliar usa término anterior à data de referência e no TMDL usa status `vencido`. O auxiliar também decompõe `Risco de Aporte` em duas medidas e usa rótulos em minúsculas, enquanto o TMDL calcula os componentes internamente e exibe `Alto`, `Médio` e `Baixo`.

| Declarações somente no DAX auxiliar | Tratamento na baseline |
|---|---|
| `Quantidade de Contratos` | Usar a contagem no grão de contrato resolvido, com filtros explícitos. |
| `Contratos Ate 30 Dias`, `Contratos Ate 90 Dias` | Usar as faixas de vencimento a partir da `as_of_date`. O alerta de ativos mantém sua população própria. |
| `Valor de Aportes`, `Quantidade de Renovacoes` | Usar o valor por tipo de aditamento e a contagem de eventos por `amendment_id`. A contagem de contratos renovados conta `contract_key`. |
| `Dependencia Financeira Media` | Descartar a média simples da razão anual como substituto da dependência de carteira. Preservar a razão por exercício e a ponderação por categoria. |
| `Excecoes de Qualidade`, `Entidades com Falha de Qualidade` | Derivar do controle por entidade e execução em `06_data_quality.sql`. |
| `Variação Valor Contratado por Categoria` | Descartar a comparação entre anos extremos. O grid vigente usa duas janelas móveis consecutivas. |
| `Percentual Consumido por Contrato`, `Percentual de Vigência Decorrida` | Reutilizar as fórmulas como componentes do risco de aporte, mantidas no grão de contrato. |

## Contratos para a consolidação

### Datas e populações

| Leitura | Parâmetro e intervalo | Resultado |
|---|---|---|
| Snapshot | Uma publicação com `source_snapshot_id`, `pipeline_run_id` e `as_of_date`. | Status, valores consolidados e controles do lote. Selecionar período de análise dentro do mesmo lote. |
| Posição acumulada | Data de corte informada, inclusive. No PBIP, o padrão vem do máximo de `dCalendar` no contexto. | Originais e aditamentos pela data efetiva, pagamentos pela data de pagamento e saldo pela diferença. Somar cada evento uma vez no seu grão. |
| Fluxo anual | Conjunto de exercícios de `dAno`. Cada ano vai de 01/01 a 31/12, inclusive. | Valor e contagem dos eventos ocorridos no conjunto. Sem filtro, o TMDL usa todos os anos disponíveis em `dAno`. A variação líquida subtrai os fluxos do mesmo período. |
| Fechamento | Ano de fechamento explícito, com corte em 31/12. No PBIP, `Ano Selecionado` usa um único ano ou o maior ano do calendário no contexto. | Saldo acumulado até o fim do exercício. Pedidos para vários exercícios retornam uma posição por exercício. |
| Janela móvel | `R = as_of_date` e `N` meses. Atual de `EDATE(R,-N)+1` a `R`. Anterior de `EDATE(R,-2N)+1` a `EDATE(R,-N)`. Limites inclusivos. | Originais e aditamentos pela data efetiva, dentro dos filtros de contrato. Padrão de 12 meses. A variação retorna `NULL` com base anterior ausente ou não positiva, conforme o dicionário. O TMDL atual só bloqueia ausência e zero. |

- O saldo de snapshot vem de `balance_value`. A posição reconstruída usa pagamentos e eventos. Sirva as duas leituras com nomes distintos. No fechamento e em janelas, some os aditamentos válidos em `vw_renewals`. Os indicadores por tipo explicitam o filtro `renovacao` ou `aporte`.
- Use `as_of_date` no card e na lista de vencimento próximo. Conte contratos de status ativo com término entre essa data e D+90. As contagens por status ativo, vencido e encerrado seguem o status do lote. Os fluxos anuais de vencimento e encerramento usam, respectivamente, término e `risk_evaluation_date` no cenário atual.
- No spending, use a data de pagamento em cards, séries, tabela e rótulo do segmentador. O rótulo vigente usa `dAno` por meio de uma medida que remove `dCalendar`, o que pode repetir o mesmo valor para anos diferentes. A participação de spending tem como base o total de pagamentos do universo filtrado antes da divisão por fornecedor. O ranking por valor contratado anual é um cálculo separado.
- Para os extremos de risco, use somente categorias com índice definido. Em empate, ordene por nome e chave de categoria. O risco ponderado preserva a fórmula de saldo positivo do modelo. Uma categoria sem base ou com numerador inteiramente ausente tem índice `NULL`. Para homologação e risco atual do fornecedor, selecione a mesma avaliação pelo critério do SQL 04.

### Financeiro por CNPJ e por categoria

1. **Exposição anual.** Por CNPJ e exercício, inclua cada contrato cuja vigência intercepte `[01/01, financial_period_end_date]`. O SQL vigente usa `total_value × 365,25 / (dias entre início e fim + 1)` e considera o valor anualizado inteiro para cada contrato elegível. A razão usa a receita daquele exercício. Para um CNPJ com registro financeiro e sem contrato elegível, o SQL publica exposição zero. Preserve as colunas públicas e identifique essa semântica como anual.
2. **Dependência da carteira ativa.** Na publicação selecionada, inclua contratos de status ativo com início ≤ `as_of_date` ≤ fim. Use a mesma anualização com vigência inclusiva em dias. Períodos ausentes ou invertidos ficam fora do cálculo. O denominador é a receita do maior `financial_period_end_date` publicado para o mesmo CNPJ. Esse fechamento pode ser posterior à `as_of_date` da simulação. Uma receita nula ou zero no último exercício produz dependência `NULL` e não aciona fallback para exercício anterior. Na cobertura, divida a receita pela carteira anualizada e retorne `NULL` quando falta receita ou quando a carteira é nula ou zero.
3. **Ponderação por categoria.** Resolva a dependência de cada CNPJ sobre sua carteira completa, no mesmo snapshot. Dentro da categoria e demais filtros de contrato, pondere cada contrato ativo com anualizado positivo por seu próprio anualizado. Inclua no denominador apenas os pesos de contratos com dependência definida. O total é calculado sobre contratos no contexto do total. Preserve a chave do CNPJ em cada cálculo e trate consolidação de grupo como regra própria. Dados de matriz e filial podem ter a mesma base financeira na fonte.
4. **Cenários e histórico.** A contagem por cenário requer um contrato ativo vigente, inclusive contrato de valor zero. A tabela financeira de fornecedores e o gráfico histórico usam a base de anualizado positivo prevista no PBIP. A tabela aplica o cálculo à carteira completa de cada fornecedor. O gráfico usa a população positiva no contexto contratual e agrega receita, custo e lucro líquido no exercício do eixo. A margem é a razão de somas e retorna `NULL` sem receita válida.

A precisão de cálculo acompanha os valores de origem. Exiba moeda em R$ com duas casas, razões como percentuais e contagens como inteiros. O formato monetário en-US de algumas declarações TMDL é configuração de apresentação. Exiba ausência como estado sem dados e use zero em contagens de um conjunto conhecido sem ocorrências. Mantenha `NULL` para razões sem denominador. O [dicionário](metric_dictionary.md) e os [contratos curated](curated_contracts.md) registram as fontes e as regras de qualidade.

## Casos de referência

As tabelas abaixo são entradas sintéticas independentes do PBIP. Datas usam ISO 8601, valores estão em reais e as saídas mantêm a precisão até a apresentação. Todos os fatos listados pertencem a uma única publicação por caso.

### A. Posição, fluxo e fechamento

Use `as_of_date = 2026-07-31`. Cada linha é um registro distinto. Os dois aditamentos de renovação pertencem ao mesmo contrato. Considere `C2` como `novo_contrato`.

| Data efetiva | Contrato | Evento | Valor |
|---|---|---|---:|
| 2024-12-31 | C1 | original | 1.000 |
| 2024-12-31 | C1 | pagamento | 100 |
| 2025-01-01 | C1 | renovação R1 | 200 |
| 2025-01-01 | C1 | pagamento | 150 |
| 2025-12-31 | C1 | renovação R2 | 40 |
| 2025-12-31 | C1 | aporte A1 | 100 |
| 2025-12-31 | C1 | pagamento | 50 |
| 2025-12-31 | C2 | original | 400 |
| 2025-12-31 | C2 | pagamento | 25 |
| 2026-01-01 | C1 | aporte A2 | 60 |
| 2026-01-01 | C1 | pagamento | 40 |
| 2026-07-31 | C2 | pagamento | 10 |

| Consulta | Resultado esperado |
|---|---|
| Fechamento de 2024 | Contratado 1.000, consumido 100, saldo 900. |
| Fluxo de 2025 | Contratado `400 + 200 + 40 + 100 = 740`, consumido `150 + 50 + 25 = 225`, variação líquida 515. |
| Contagens de 2025 | Dois eventos de renovação e um contrato renovado (C1). Um contrato novo (C2). |
| Fechamento de 2025 | Contratado `1.000 + 740 = 1.740`, consumido `100 + 225 = 325`, saldo `900 + 515 = 1.415`. |
| Posição em 2026-01-01 | Contratado `1.740 + 60 = 1.800`, consumido `325 + 40 = 365`, saldo 1.435. |
| Posição em 2026-07-31 | Contratado 1.800, consumido `365 + 10 = 375`, saldo 1.425. |
| Fluxo de 2024 e 2025 juntos | Contratado 1.740, consumido 325, variação líquida 1.415 no conjunto. Se o pedido for por fechamento, retorne as duas posições separadamente. |

### B. Fronteiras da janela móvel

Use `as_of_date = 2026-07-31`, categoria X e janela de 6 meses. A janela anterior é 2025-08-01 a 2026-01-31 e a atual é 2026-02-01 a 2026-07-31.

| Data | Evento | Valor | Janela de 6 meses |
|---|---|---:|---|
| 2025-07-31 | original | 900 | Fora |
| 2025-08-01 | original | 100 | Anterior |
| 2026-01-31 | renovação | 50 | Anterior |
| 2026-02-01 | original | 80 | Atual |
| 2026-07-31 | aporte | 120 | Atual |
| 2026-08-01 | aporte | 900 | Fora |

A janela anterior soma 150, a atual soma 200 e a variação é `(200 − 150) / 150 = 1/3`, exibida como 33,3%. O contratado 12M soma 350 no intervalo de 2025-08-01 a 2026-07-31. Sem linhas na janela anterior ou com total anterior zero, a variação é `NULL`. Se o único valor anterior de uma categoria for um ajuste de −50, a regra de base positiva também retorna `NULL`.

### C. Exposição anual, carteira ativa e filtro de categoria

Use `as_of_date = 2026-07-31`. M é a matriz e F é a filial do mesmo grupo. Z tem receita zero, N não tem registro financeiro e P tem um contrato ativo de valor zero. Os códigos representam CNPJs distintos.

| Contrato | CNPJ | Categoria | Status | Início | Fim | Valor total |
|---|---|---|---|---|---|---:|
| M0 | M | A | encerrado | 2026-01-01 | 2026-03-31 | 90 |
| M1 | M | A | ativo | 2026-01-01 | 2026-12-31 | 365 |
| M2 | M | B | ativo | 2026-01-01 | 2026-12-31 | 730 |
| F1 | F | A | ativo | 2026-01-01 | 2026-12-31 | 365 |
| Z1 | Z | A | ativo | 2026-01-01 | 2026-12-31 | 365 |
| N1 | N | A | ativo | 2026-01-01 | 2026-12-31 | 365 |
| P1 | P | A | ativo | 2026-01-01 | 2026-12-31 | 0 |

| CNPJ | Fechamento financeiro | Receita |
|---|---|---:|
| M | 2025-12-31 | 5.000 |
| M | 2026-12-31 | 3.652,50 |
| F | 2026-12-31 | 1.461,00 |
| Z | 2025-12-31 | 1.000 |
| Z | 2026-12-31 | 0 |
| P | 2026-12-31 | 1.000 |

| Consulta | Resultado esperado |
|---|---|
| Exposição fiscal de M em 2026 | M0 dura 90 dias e contribui `90 × 365,25 / 90 = 365,25`. Com M1 e M2, a soma é `365,25 + 365,25 + 730,50 = 1.461,00` e a razão é 40%. |
| Dependência ativa de M | M1 e M2 contribuem 365,25 e 730,50. `1.095,75 / 3.652,50 = 30%`, inclusive ao calcular a relação do CNPJ em um contrato da categoria A. |
| Dependência ativa de F | `365,25 / 1.461 = 25%`. A filial usa a própria receita. |
| Dependência ativa de Z e N | `NULL` para ambos. Z tem o último exercício publicado com receita zero. N tem carteira anualizada de 365,25 e receita ausente. |
| Categoria A | Pesos de M1 e F1 de 365,25 cada. M0 está fora da carteira ativa, Z1 e N1 não têm razão válida e P1 tem peso zero. O resultado é `(365,25 × 30% + 365,25 × 25%) / 730,50 = 27,5%`. |
| Categoria B e total | B tem somente M2 e retorna 30%. No total o peso de M é 1.095,75 e o de F é 365,25, resultando em 28,75% antes do arredondamento. |
| População financeira | Cinco CNPJs têm contrato ativo vigente e quatro têm anualizado positivo. P entra na contagem de cenários e fica fora da população de valor positivo. Em uma seleção que contenha apenas Z e N, a dependência ponderada é `NULL`. |

### D. Alertas, estados vazios e desempate

- Com referência 2026-07-31, use contratos ativos com término em 2026-07-30, 2026-07-31, 2026-10-29 e 2026-10-30, e um contrato encerrado com término em 2026-07-31. O alerta de 90 dias inclui somente os ativos com término em D+0 e D+90. A faixa cronológica do SQL 02 marca 2026-07-30 como vencido pela data, independentemente do status do lote.
- No mesmo CNPJ, suponha duas avaliações em 2026-07-10 com IDs `AV-01` (status `pendente`, risco `alto`) e `AV-02` (status `aprovado`, risco `baixo`). O SQL seleciona `AV-02` e preserva o par de atributos do registro. Para um fornecedor sem avaliação, ambos os campos são `NULL`.
- Para um contrato ativo com diferença de 100 dias entre início e fim e 50 dias decorridos na `as_of_date`, use `total_value = 1.000`. Saldos de 300, 450 e 451 produzem consumo de 70%, 55% e 54,9% e desvio de +20, +5 e +4,9 p.p. Os rótulos são, respectivamente, Alto, Médio e Baixo. Com valor total zero ou vigência de duração não positiva, o risco de aporte é `NULL`.

### Evidência da verificação

As medidas foram conferidas por nome e linha contra os TMDL, cruzadas com as referências estáticas do relatório. Os casos foram recalculados a partir das entradas acima, com aritmética decimal e comparação de datas, e os comportamentos vigentes selecionados foram exercitados em DuckDB. A comparação dinâmica com o PBIP e a implementação das consultas parametrizadas pertencem às próximas entregas.
