-- KPI: carteira contratada, saldo e percentual de consumo por fornecedor e categoria.
SELECT
    supplier_legal_name,
    category_macro_group,
    COUNT(*) AS contract_count,
    SUM(total_value) AS contracted_value,
    SUM(balance_value) AS contract_balance_value,
    SUM(total_value - balance_value) AS consumed_contract_value,
    SUM(total_value - balance_value) / NULLIF(SUM(total_value), 0) AS consumption_percentage
FROM vw_contracts
GROUP BY supplier_legal_name, category_macro_group
ORDER BY contracted_value DESC, supplier_legal_name;
