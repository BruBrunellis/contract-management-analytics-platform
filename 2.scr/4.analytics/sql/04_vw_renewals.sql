CREATE OR REPLACE VIEW vw_renewals AS
SELECT
    renewal.renewal_key,
    renewal.amendment_id,
    renewal.amendment_sequence,
    renewal.amendment_type,
    renewal.is_renewal,
    renewal.amendment_value,
    contract.contract_key,
    contract.contract_id,
    supplier.supplier_key,
    supplier.supplier_legal_name,
    category.category_key,
    category.category_code,
    start_calendar.calendar_date AS validity_start_date,
    end_calendar.calendar_date AS validity_end_date
FROM src_fact_renewal AS renewal
INNER JOIN src_dim_contract AS contract
    ON renewal.contract_key = contract.contract_key
INNER JOIN src_dim_supplier AS supplier
    ON renewal.supplier_key = supplier.supplier_key
INNER JOIN src_dim_category AS category
    ON renewal.category_key = category.category_key
LEFT JOIN src_dim_calendar AS start_calendar
    ON renewal.validity_start_calendar_key = start_calendar.calendar_key
LEFT JOIN src_dim_calendar AS end_calendar
    ON renewal.validity_end_calendar_key = end_calendar.calendar_key;
