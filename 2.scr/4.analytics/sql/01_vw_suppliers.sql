CREATE OR REPLACE VIEW vw_suppliers AS
SELECT
    supplier.supplier_key,
    supplier.supplier_cnpj,
    supplier.supplier_legal_name,
    supplier.supplier_hierarchy,
    supplier.company_size,
    supplier.economic_activity,
    supplier.economic_group_key,
    economic_group.economic_group_legal_name,
    supplier.parent_supplier_key,
    supplier.financial_scenario
FROM src_dim_supplier AS supplier
LEFT JOIN src_dim_economic_group AS economic_group
    USING (economic_group_key);
