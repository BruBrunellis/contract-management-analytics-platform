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

## Execução

```powershell
python .\2.src\4.analytics\build_analytics.py `
  --etl-manifest .\1.data\3.curated\<pipeline_run_id>\etl_manifest.json
```

Por padrão, o banco é gravado em
`1.data/4.analytics/<pipeline_run_id>/contract_analytics.duckdb`. Use `--database`
para informar outro caminho local.
