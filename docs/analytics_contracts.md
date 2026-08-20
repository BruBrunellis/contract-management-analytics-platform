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

As consultas de KPI ficam em `2.scr/4.analytics/kpis/` e são executadas sobre
essas views. Consulte o [dicionário de métricas](metric_dictionary.md) para
fórmulas, grão e tratamento de exceções.

## Execução

```powershell
python .\2.scr\4.analytics\build_analytics.py `
  --etl-manifest .\1.data\3.curated\<pipeline_run_id>\etl_manifest.json
```

Por padrão, o banco é gravado em
`1.data/4.analytics/<pipeline_run_id>/contract_analytics.duckdb`. Use `--database`
para informar outro caminho local.
