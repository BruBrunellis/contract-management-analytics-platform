CREATE OR REPLACE VIEW vw_contracts AS
SELECT
    contract.contract_key,
    contract.contract_id,
    contract.contract_name,
    contract.contract_type,
    contract.contract_status,
    contract.final_risk,
    contract.original_value,
    contract.total_value,
    contract.balance_value,
    supplier.supplier_key,
    supplier.supplier_legal_name,
    supplier.economic_group_key,
    category.category_key,
    category.category_code,
    category.category_name,
    category.category_macro_group,
    category.category_group,
    category.category_family,
    start_calendar.calendar_date AS validity_start_date,
    end_calendar.calendar_date AS validity_end_date
FROM src_dim_contract AS contract
INNER JOIN src_dim_supplier AS supplier
    USING (supplier_key)
INNER JOIN src_dim_category AS category
    USING (category_key)
LEFT JOIN src_dim_calendar AS start_calendar
    ON contract.validity_start_calendar_key = start_calendar.calendar_key
LEFT JOIN src_dim_calendar AS end_calendar
    ON contract.validity_end_calendar_key = end_calendar.calendar_key;
