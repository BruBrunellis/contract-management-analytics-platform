CREATE OR REPLACE VIEW vw_spending AS
SELECT
    spending.spending_key,
    spending.payment_id,
    spending.payment_value,
    spending.cost_center,
    calendar.calendar_date AS payment_date,
    contract.contract_key,
    contract.contract_id,
    contract.contract_status,
    supplier.supplier_key,
    supplier.supplier_legal_name,
    supplier.economic_group_key,
    category.category_key,
    category.category_code,
    category.category_name,
    category.category_macro_group
FROM src_fact_spending AS spending
INNER JOIN src_dim_contract AS contract
    ON spending.contract_key = contract.contract_key
INNER JOIN src_dim_supplier AS supplier
    ON spending.supplier_key = supplier.supplier_key
INNER JOIN src_dim_category AS category
    ON spending.category_key = category.category_key
LEFT JOIN src_dim_calendar AS calendar
    ON spending.payment_calendar_key = calendar.calendar_key;
