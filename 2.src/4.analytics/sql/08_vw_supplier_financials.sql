CREATE OR REPLACE VIEW vw_supplier_financials AS
WITH annualized_contracts AS (
    SELECT
        financial.supplier_key,
        financial.financial_year,
        SUM(
            contract.total_value
            / NULLIF(
                DATE_DIFF('day', contract_start.calendar_date, contract_end.calendar_date) + 1,
                0
            )
            * 365.25
        ) AS annualized_contract_value
    FROM src_fact_supplier_financial AS financial
    INNER JOIN src_dim_calendar AS financial_period
        ON financial.financial_period_calendar_key = financial_period.calendar_key
    INNER JOIN src_dim_contract AS contract
        ON financial.supplier_key = contract.supplier_key
    INNER JOIN src_dim_calendar AS contract_start
        ON contract.validity_start_calendar_key = contract_start.calendar_key
    INNER JOIN src_dim_calendar AS contract_end
        ON contract.validity_end_calendar_key = contract_end.calendar_key
    WHERE contract_start.calendar_date <= financial_period.calendar_date
      AND contract_end.calendar_date >= DATE_TRUNC('year', financial_period.calendar_date)
    GROUP BY financial.supplier_key, financial.financial_year
)
SELECT
    financial.financial_snapshot_key,
    financial.financial_year,
    financial_period.calendar_date AS financial_period_end_date,
    financial.gross_revenue,
    financial.total_cost,
    financial.payroll_cost,
    financial.gross_profit,
    financial.debt_interest,
    financial.net_income,
    financial.gross_profit / NULLIF(financial.gross_revenue, 0) AS gross_margin,
    financial.net_income / NULLIF(financial.gross_revenue, 0) AS net_margin,
    COALESCE(contract.annualized_contract_value, 0) AS annualized_contract_value,
    COALESCE(contract.annualized_contract_value, 0) / NULLIF(financial.gross_revenue, 0)
        AS financial_dependency_ratio,
    financial.gross_revenue / NULLIF(contract.annualized_contract_value, 0)
        AS revenue_to_contract_coverage_ratio,
    supplier.supplier_key,
    supplier.supplier_cnpj,
    supplier.supplier_legal_name,
    supplier.supplier_hierarchy,
    supplier.economic_group_key,
    economic_group.economic_group_legal_name
FROM src_fact_supplier_financial AS financial
INNER JOIN src_dim_supplier AS supplier
    ON financial.supplier_key = supplier.supplier_key
LEFT JOIN src_dim_economic_group AS economic_group
    ON financial.economic_group_key = economic_group.economic_group_key
LEFT JOIN src_dim_calendar AS financial_period
    ON financial.financial_period_calendar_key = financial_period.calendar_key
LEFT JOIN annualized_contracts AS contract
    ON financial.supplier_key = contract.supplier_key
   AND financial.financial_year = contract.financial_year;
