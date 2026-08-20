-- KPI: capacidade financeira e dependência da carteira contratual por fornecedor e ano.
SELECT
    financial_year,
    supplier_key,
    supplier_cnpj,
    supplier_legal_name,
    economic_group_key,
    gross_revenue,
    total_cost,
    gross_profit,
    net_income,
    annualized_contract_value,
    financial_dependency_ratio,
    revenue_to_contract_coverage_ratio
FROM vw_supplier_financials
ORDER BY financial_year DESC, financial_dependency_ratio DESC NULLS LAST, supplier_legal_name;
