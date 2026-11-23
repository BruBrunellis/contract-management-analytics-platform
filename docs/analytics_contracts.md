# Contratos da camada analítica

## Entrada e rastreabilidade

`build_analytics.py` recebe um `etl_manifest.json` aprovado. O manifesto define o
diretório curated, o `pipeline_run_id`, o `source_snapshot_id` e o cenário. O
construtor rejeita manifestos com quality gate reprovado ou Parquets ausentes.

O banco criado contém a tabela `analytics_run_context`, com o contexto exato da
execução. As views leem exclusivamente os Parquets curated declarados pelo
manifesto.

## Views públicas

| View | Grão | Fontes curated |
|---|---|---|
| `vw_suppliers` | Fornecedor legal | `dim_supplier`, `dim_economic_group` |
| `vw_contracts` | Contrato resolvido | `dim_contract` e dimensões relacionadas |
| `vw_spending` | Pagamento | `fact_spending` e dimensões relacionadas |
| `vw_rfi` | Avaliação de homologação e risco | `fact_rfi`, fornecedor e calendário |
| `vw_renewals` | Aditamento | `fact_renewal` e dimensões relacionadas |
| `vw_supplier_financials` | Fornecedor legal e ano fiscal | `fact_supplier_financial`, contratos e dimensões |
| `vw_quality_reconciliation` | Controle por entidade | relatório de reconciliação curated |
| `vw_quality_exceptions` | Exceção publicada | índice consolidado de exceções |

As views de pagamentos e renovações fazem joins apenas com dimensões. Não há join
direto entre fatos, preservando seus grãos independentes.

As views de contratos, pagamentos e renovações expõem a hierarquia completa de
categoria (`category_macro_group`, `category_group`, `category_family` e
`category_name`) para consumo direto do dashboard sem recorrer às views internas
`src_*`.

As consultas de KPI ficam em `2.src/4.analytics/kpis/` e são executadas sobre
essas views. Consulte o [dicionário de métricas](metric_dictionary.md) para
fórmulas, grão e tratamento de exceções.

## Consultas de métricas v1

O build instala macros de tabela no DuckDB junto com as views. As assinaturas
abaixo formam a interface v1 para consultas, com as regras do
[inventário SQL/DAX](metric_baseline.md#contratos-para-a-consolidação).
Para consultar as macros em uma publicação anterior, reconstrua o banco pelo
manifesto correspondente. As views consumidas pelo PBIP e os seis arquivos
de KPI continuam disponíveis com seus contratos existentes.

`p_suppliers` e `p_categories` aceitam listas opcionais de chaves
(`VARCHAR[]`). `NULL` representa todos os valores e a lista vazia
representa uma seleção vazia. Os fatos são selecionados pelas chaves do
contrato. Para solicitar uma categoria por vez, passe sua chave na lista.

| Macro | Parâmetros além dos filtros de chaves | Saída |
|---|---|---|
| `metric_contract_position` | `p_cutoff` com uma data inclusiva | Uma posição acumulada com valor original, aditamentos, contratado, pago e saldo. |
| `metric_contract_annual_flow` | `p_years` como `INTEGER[]` | Fluxos e contagens no conjunto de exercícios, com contratos renovados distintos e contagem de eventos. |
| `metric_contract_year_close` | `p_years` como `INTEGER[]` | Uma posição acumulada por exercício, com data de corte em 31/12. |
| `metric_contract_rolling` | `p_months` com 6, 12, 24, 36 ou 48, padrão 12 | Duas janelas consecutivas até a `as_of_date` e a variação de contratado. A razão é nula sem base anterior positiva. |
| `metric_annual_supplier_ranking` | `p_years` como `INTEGER[]` | Contratado por fornecedor e ranking denso na seleção. |
| `metric_contract_expiry` | Apenas filtros de chaves | Uma linha por contrato com dias até o vencimento, faixa e indicador do alerta de ativos até 90 dias. |
| `metric_contract_snapshot` | Apenas filtros de chaves | Carteira, saldo e consumo do snapshot, contagens por status e alerta de vencimento. |
| `metric_spending_payments` | `p_start` e `p_end` como datas inclusivas | Um registro por pagamento datado, para compor séries e detalhe. |
| `metric_spending` | `p_start` e `p_end` como datas inclusivas | Gastos por fornecedor, ranking denso e participação no total filtrado. |

Os anos omitidos usam o intervalo entre as datas dos eventos da publicação.
Posições e fluxos ficam nulos sem valores na seleção. As contagens retornam
zero sem ocorrências. Os limites omitidos em gastos deixam o respectivo lado
do intervalo aberto.

```sql
SELECT * FROM metric_contract_annual_flow([2025, 2026], p_categories := ['CAT-01']);
SELECT * FROM metric_contract_position(DATE '2026-07-31');
SELECT * FROM metric_contract_rolling(6, p_categories := ['CAT-01']);
```

### Financeiro e risco

| Macro | Parâmetros | Saída |
|---|---|---|
| `metric_supplier_annual_exposure` | `p_years`, `p_suppliers` | Exposição, razão e cobertura por CNPJ e exercício. Usa as colunas financeiras anuais da view pública. |
| `metric_supplier_active_dependency` | `p_suppliers` | Carteira completa ativa por CNPJ, quantidade de contratos, data da última receita publicada, dependência e cobertura. |
| `metric_category_active_dependency` | `p_suppliers`, `p_categories` | Dependência ponderada pelos contratos ativos elegíveis de cada categoria e do total. |
| `metric_supplier_financial_scenarios` | `p_suppliers`, `p_categories` | Contagem por cenário de CNPJs com contrato ativo e vigente. |
| `metric_supplier_financial_history` | `p_years`, `p_suppliers`, `p_categories` | Receita, custo, lucro líquido e margem por exercício dos CNPJs com anualizado ativo positivo na seleção. |
| `metric_supplier_latest_rfi` | `p_suppliers` | Última avaliação de cada CNPJ avaliado, com desempate pelo maior ID de avaliação. |
| `metric_category_risk` | `p_suppliers`, `p_categories` | Índice ponderado pelo saldo positivo e contagem por nível de risco, por categoria e total. |
| `metric_category_risk_extremes` | `p_suppliers`, `p_categories` | Valor, chave e nome das categorias com maior e menor índice definido. |
| `metric_contract_funding_risk` | `p_suppliers`, `p_categories` | Percentual de saldo, percentual consumido, vigência decorrida e risco de aporte por contrato ativo. |
| `metric_high_risk_exposure` | `p_suppliers`, `p_categories` | Contratado dos últimos 12 meses, contratado de fornecedores com risco alto e razão entre os dois. |

Nos dois resultados com `is_total`, a linha do total recalcula a métrica no
conjunto filtrado. A dependência de cada fornecedor é calculada no conjunto
de seus contratos ativos, e o filtro de categoria restringe os pesos.
`p_years` omitido nas consultas financeiras usa os exercícios publicados.
Ausência ou zero de receita recente produz dependência nula por CNPJ. A
cobertura retorna zero quando a receita conhecida é zero e a carteira tem
valor diferente de zero.

```sql
SELECT * FROM metric_supplier_annual_exposure([2026], ['SUP-01']);
SELECT * FROM metric_supplier_active_dependency(['SUP-01']);
SELECT * FROM metric_category_active_dependency(p_categories := ['CAT-01']);
```

### Compatibilidade com Power BI

O PBIP continua a importar as views públicas pelo mesmo DSN. Em particular,
`vw_supplier_financials.annualized_contract_value` e
`financial_dependency_ratio` continuam descrevendo o exercício financeiro.
Os nomes explícitos da exposição anual e os indicadores da carteira ativa
estão disponíveis nas consultas v1.

| Divergência no PBIP versionado | Regra das consultas v1 |
|---|---|
| O card de vencimento usa `TODAY()` e a lista usa a data da publicação. | Card e lista podem usar o mesmo indicador calculado pela `as_of_date`. |
| O rótulo do segmentador de spending pode usar os fluxos de `dAno` em vez da seleção de pagamentos. | O valor de cada período vem da data do pagamento. |
| O ranking anual agrupa por razão social. | A classificação agrupa pela chave do fornecedor. |
| A variação móvel em DAX aceita base anterior negativa. | A variação exige base anterior positiva. |
| Risco e status de homologação podem escolher atributos de registros diferentes na mesma data. | Ambos vêm da avaliação com a maior data e o maior ID em caso de empate. |
| O menor risco pode apontar para uma categoria com índice em branco. | Os extremos consideram somente índices definidos e desempate por nome e chave. |

A reconciliação usa os [casos de referência](metric_baseline.md#casos-de-referência)
e os testes de consultas DuckDB. A comparação com as expressões e filtros PBIP
é baseada na definição versionada do modelo.

## Execução

```powershell
python .\2.src\4.analytics\build_analytics.py `
  --etl-manifest .\1.data\3.curated\<pipeline_run_id>\etl_manifest.json
```

Por padrão, o banco é gravado em
`1.data/4.analytics/<pipeline_run_id>/contract_analytics.duckdb`. Use `--database`
para informar outro caminho local.
