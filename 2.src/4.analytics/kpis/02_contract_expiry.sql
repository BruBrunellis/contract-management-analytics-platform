-- KPI: contratos vencidos e a vencer, usando a data de referência do snapshot.
WITH reference_date AS (
    SELECT as_of_date
    FROM analytics_run_context
)
SELECT
    contract_id,
    contract_name,
    supplier_legal_name,
    contract_status,
    validity_end_date,
    total_value,
    balance_value,
    DATE_DIFF('day', reference_date.as_of_date, validity_end_date) AS days_to_expiry,
    CASE
        WHEN validity_end_date < reference_date.as_of_date THEN 'expired'
        WHEN validity_end_date <= reference_date.as_of_date + INTERVAL 30 DAY THEN 'expires_in_30_days'
        WHEN validity_end_date <= reference_date.as_of_date + INTERVAL 60 DAY THEN 'expires_in_60_days'
        WHEN validity_end_date <= reference_date.as_of_date + INTERVAL 90 DAY THEN 'expires_in_90_days'
        ELSE 'outside_renewal_window'
    END AS expiry_status
FROM vw_contracts
CROSS JOIN reference_date
ORDER BY validity_end_date, contract_id;
