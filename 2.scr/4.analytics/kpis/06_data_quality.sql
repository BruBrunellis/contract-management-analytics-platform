-- KPI: qualidade do lote aprovado, preservando reconciliações e exceções explicitamente.
SELECT
    reconciliation.entity,
    reconciliation.status,
    reconciliation.match_rate,
    reconciliation.row_count_delta,
    reconciliation.monetary_delta,
    reconciliation.failure_reasons,
    COALESCE(exceptions.exception_count, 0) AS exception_count
FROM vw_quality_reconciliation AS reconciliation
LEFT JOIN (
    SELECT entity, COUNT(*) AS exception_count
    FROM vw_quality_exceptions
    GROUP BY entity
) AS exceptions
    ON reconciliation.entity = exceptions.entity
ORDER BY reconciliation.status DESC, reconciliation.entity;
