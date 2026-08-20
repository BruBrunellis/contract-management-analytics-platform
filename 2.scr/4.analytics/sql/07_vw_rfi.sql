CREATE OR REPLACE VIEW vw_rfi AS
SELECT
    rfi.rfi_key,
    rfi.risk_assessment_id,
    assessment.calendar_date AS assessment_date,
    approval.calendar_date AS last_approval_date,
    expiration.calendar_date AS expiration_date,
    rfi.homologation_result,
    rfi.homologation_status,
    rfi.financial_risk,
    rfi.labor_risk,
    rfi.credit_rating,
    rfi.final_risk,
    rfi.interest_to_revenue_ratio,
    rfi.revenue_trend,
    rfi.net_margin,
    rfi.labor_cases_index,
    supplier.supplier_key,
    supplier.supplier_cnpj,
    supplier.supplier_legal_name,
    supplier.economic_group_key
FROM src_fact_rfi AS rfi
INNER JOIN src_dim_supplier AS supplier
    ON rfi.supplier_key = supplier.supplier_key
LEFT JOIN src_dim_calendar AS assessment
    ON rfi.assessment_calendar_key = assessment.calendar_key
LEFT JOIN src_dim_calendar AS approval
    ON rfi.last_approval_calendar_key = approval.calendar_key
LEFT JOIN src_dim_calendar AS expiration
    ON rfi.expiration_calendar_key = expiration.calendar_key;
