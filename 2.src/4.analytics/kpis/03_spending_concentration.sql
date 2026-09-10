-- KPI: concentração de gastos por grupo econômico e fornecedor legal.
WITH spending_by_supplier AS (
    SELECT
        economic_group_key,
        supplier_legal_name,
        SUM(payment_value) AS total_spending
    FROM vw_spending
    GROUP BY economic_group_key, supplier_legal_name
),
portfolio AS (
    SELECT SUM(total_spending) AS portfolio_spending
    FROM spending_by_supplier
)
SELECT
    spending_by_supplier.*,
    total_spending / NULLIF(portfolio.portfolio_spending, 0) AS spending_concentration_ratio,
    DENSE_RANK() OVER (ORDER BY total_spending DESC) AS spending_rank
FROM spending_by_supplier
CROSS JOIN portfolio
ORDER BY spending_rank, supplier_legal_name;
