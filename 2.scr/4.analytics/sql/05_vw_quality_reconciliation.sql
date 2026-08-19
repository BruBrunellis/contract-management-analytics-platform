CREATE OR REPLACE VIEW vw_quality_reconciliation AS
SELECT
    pipeline_run_id,
    source_snapshot_id,
    entity,
    reconciliation_type,
    source_table,
    curated_table,
    source_row_count,
    published_row_count,
    exception_row_count,
    match_rate,
    row_count_delta,
    source_monetary_total,
    curated_monetary_total,
    exception_monetary_total,
    monetary_delta,
    status,
    failure_reasons
FROM src_quality_reconciliation;
