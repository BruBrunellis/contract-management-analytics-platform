-- KPI: avaliação de homologação e risco mais recente por fornecedor legal.
WITH ranked_rfi AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY supplier_key
            ORDER BY assessment_date DESC, risk_assessment_id DESC
        ) AS assessment_rank
    FROM vw_rfi
)
SELECT
    supplier_key,
    supplier_cnpj,
    supplier_legal_name,
    economic_group_key,
    assessment_date,
    expiration_date,
    homologation_result,
    homologation_status,
    financial_risk,
    labor_risk,
    credit_rating,
    final_risk,
    interest_to_revenue_ratio,
    revenue_trend,
    net_margin,
    labor_cases_index
FROM ranked_rfi
WHERE assessment_rank = 1
ORDER BY
    CASE final_risk
        WHEN 'alto' THEN 3
        WHEN 'medio' THEN 2
        WHEN 'baixo' THEN 1
        ELSE 0
    END DESC,
    supplier_legal_name;
