# Quality gate da camada Curated

O quality gate consolida a auditabilidade das dimensões e fatos publicados em cada lote. Ele é executado após todas as transformações curated e antes da conclusão bem-sucedida do pipeline.

## Artefatos

| Arquivo | Conteúdo |
|---|---|
| `curated_reconciliation_report_<lote>.parquet` | Controles de contagem, match rate, totais financeiros e status por entidade. |
| `curated_exception_index_<lote>.parquet` | Índice das exceções detalhadas, com causa, chave de negócio e linhagem. |

O relatório concilia `dim_supplier`, `dim_contract`, `fact_spending`, `fact_rfi` e `fact_renewal` contra as respectivas fontes staging. Também valida os invariantes de `dim_economic_group`, `dim_calendar` e `dim_category`.

## Limiares

Os parâmetros pertencem ao `PipelineConfig` e podem ser definidos em arquivo JSON:

| Parâmetro | Padrão | Regra |
|---|---:|---|
| `min_curated_match_rate` | `0.95` | Percentual mínimo de registros publicados por entidade. |
| `financial_reconciliation_tolerance` | `0.0` | Diferença financeira máxima tolerada em pagamentos e aditamentos. |

A cobertura de origem precisa ser exata: cada registro staging deve ter sido publicado ou direcionado para exceção. O relatório e o manifesto são gravados antes de o pipeline lançar `CuratedQualityError` quando uma entidade não cumprir seus limiares.
