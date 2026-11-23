CREATE OR REPLACE MACRO _metric_contract_scope(p_suppliers, p_categories) AS TABLE
    SELECT c.*
    FROM vw_contracts AS c
    WHERE (p_suppliers IS NULL OR list_contains(p_suppliers::VARCHAR[], c.supplier_key))
      AND (p_categories IS NULL OR list_contains(p_categories::VARCHAR[], c.category_key));

-- A categoria e o fornecedor seguem o contrato, como no modelo semântico.
CREATE OR REPLACE MACRO _metric_events(p_suppliers, p_categories) AS TABLE
    WITH contracts AS (
        SELECT * FROM _metric_contract_scope(p_suppliers, p_categories)
    )
    SELECT supplier_key, category_key, contract_key, validity_start_date AS event_date,
           'original' AS event_kind, contract_type AS event_type, original_value AS event_value
    FROM contracts
    UNION ALL
    SELECT c.supplier_key, c.category_key, c.contract_key, r.validity_start_date,
           'amendment', r.amendment_type, r.amendment_value
    FROM vw_renewals AS r
    JOIN contracts AS c USING (contract_key)
    UNION ALL
    SELECT c.supplier_key, c.category_key, c.contract_key, s.payment_date,
           'payment', NULL, s.payment_value
    FROM vw_spending AS s
    JOIN contracts AS c USING (contract_key);

CREATE OR REPLACE MACRO _metric_years(p_years) AS TABLE
    WITH bounds AS (
        SELECT year(min(event_date)) AS first_year, year(max(event_date)) AS last_year
        FROM _metric_events(NULL, NULL)
        WHERE p_years IS NULL
    )
    SELECT DISTINCT unnest(
        coalesce(p_years::INTEGER[], range(first_year, last_year + 1)::INTEGER[])
    ) AS fiscal_year
    FROM bounds;

CREATE OR REPLACE MACRO _metric_summarize_events(p_start, p_end, p_years, p_suppliers, p_categories)
AS TABLE
    SELECT
        sum(event_value) FILTER (event_kind = 'original') AS original_value,
        sum(event_value) FILTER (event_kind = 'amendment') AS amendment_value,
        sum(event_value) FILTER (
            event_kind = 'amendment' AND event_type = 'renovacao'
        ) AS renewal_value,
        sum(event_value) FILTER (
            event_kind = 'amendment' AND event_type = 'aporte'
        ) AS additional_value,
        sum(event_value) FILTER (event_kind <> 'payment') AS contracted_value,
        sum(event_value) FILTER (event_kind = 'payment') AS paid_value,
        count(DISTINCT contract_key) FILTER (
            event_kind = 'original' AND event_type = 'novo_contrato'
        ) AS new_contract_count,
        count(DISTINCT contract_key) FILTER (
            event_kind = 'amendment' AND event_type = 'renovacao'
        ) AS renewed_contract_count,
        count(*) FILTER (
            event_kind = 'amendment' AND event_type = 'renovacao'
        ) AS renewal_event_count
    FROM _metric_events(p_suppliers, p_categories)
    WHERE event_date IS NOT NULL
      AND (p_start IS NULL OR event_date >= p_start::DATE)
      AND (p_end IS NULL OR event_date <= p_end::DATE)
      AND (p_years IS NULL OR list_contains(p_years::INTEGER[], year(event_date)));

CREATE OR REPLACE MACRO _metric_net(p_contracted, p_paid) AS
    CASE WHEN p_contracted IS NOT NULL OR p_paid IS NOT NULL
         THEN coalesce(p_contracted, 0) - coalesce(p_paid, 0)
    END;

CREATE OR REPLACE MACRO metric_contract_position(
    p_cutoff, p_suppliers := NULL::VARCHAR[], p_categories := NULL::VARCHAR[]
) AS TABLE
    SELECT p_cutoff::DATE AS cutoff_date,
           original_value, amendment_value, renewal_value, additional_value,
           contracted_value, paid_value, _metric_net(contracted_value, paid_value) AS balance_value
    FROM _metric_summarize_events(NULL, p_cutoff, NULL, p_suppliers, p_categories)
    WHERE p_cutoff IS NOT NULL;

CREATE OR REPLACE MACRO metric_contract_annual_flow(
    p_years := NULL::INTEGER[], p_suppliers := NULL::VARCHAR[], p_categories := NULL::VARCHAR[]
) AS TABLE
    WITH selected_years AS (
        SELECT coalesce(list(fiscal_year), []::INTEGER[]) AS years
        FROM _metric_years(p_years)
    ),
    status_events AS (
        SELECT
            count(*) FILTER (
                contract_status = 'vencido' AND list_contains(years, year(validity_end_date))
            ) AS expired_contract_count,
            count(*) FILTER (
                contract_status = 'encerrado' AND list_contains(years, year(risk_evaluation_date))
            ) AS closed_contract_count
        FROM _metric_contract_scope(p_suppliers, p_categories)
        CROSS JOIN selected_years
    )
    SELECT totals.*, _metric_net(contracted_value, paid_value) AS net_flow_value, status_events.*
    FROM selected_years
    CROSS JOIN LATERAL _metric_summarize_events(NULL, NULL, years, p_suppliers, p_categories)
        AS totals
    CROSS JOIN status_events;

CREATE OR REPLACE MACRO metric_contract_year_close(
    p_years := NULL::INTEGER[], p_suppliers := NULL::VARCHAR[], p_categories := NULL::VARCHAR[]
) AS TABLE
    SELECT age.fiscal_year, position.*
    FROM _metric_years(p_years) AS age
    CROSS JOIN LATERAL metric_contract_position(
        make_date(age.fiscal_year, 12, 31), p_suppliers, p_categories
    ) AS position
    ORDER BY age.fiscal_year;

CREATE OR REPLACE MACRO metric_contract_rolling(
    p_months := 12, p_suppliers := NULL::VARCHAR[], p_categories := NULL::VARCHAR[]
) AS TABLE
    WITH reference AS (
        SELECT as_of_date,
               CASE WHEN p_months IN (6, 12, 24, 36, 48) THEN p_months::INTEGER
                    ELSE error('A janela deve ter 6, 12, 24, 36 ou 48 meses.')
               END AS months
        FROM analytics_run_context
    ),
    bounds AS (
        SELECT as_of_date,
               (as_of_date - to_months(months))::DATE AS previous_end,
               (as_of_date - to_months(2 * months))::DATE + 1 AS previous_start
        FROM reference
    )
    SELECT previous_start, previous_end, previous_end + 1 AS current_start,
           as_of_date AS current_end,
           prev.contracted_value AS previous_contracted_value,
           curr.contracted_value AS current_contracted_value,
           CASE WHEN prev.contracted_value > 0 THEN
               (_metric_net(curr.contracted_value, prev.contracted_value))
                   / prev.contracted_value
           END AS growth_ratio
    FROM bounds
    CROSS JOIN LATERAL _metric_summarize_events(
        previous_start, previous_end, NULL, p_suppliers, p_categories
    ) AS prev
    CROSS JOIN LATERAL _metric_summarize_events(
        previous_end + 1, as_of_date, NULL, p_suppliers, p_categories
    ) AS curr;

CREATE OR REPLACE MACRO metric_annual_supplier_ranking(
    p_years := NULL::INTEGER[], p_suppliers := NULL::VARCHAR[], p_categories := NULL::VARCHAR[]
) AS TABLE
    WITH contracted AS (
        SELECT supplier_key, sum(event_value) AS contracted_value
        FROM _metric_events(p_suppliers, p_categories)
        WHERE event_kind <> 'payment'
          AND year(event_date) IN (SELECT fiscal_year FROM _metric_years(p_years))
        GROUP BY supplier_key
    )
    SELECT supplier_key, contracted_value,
           dense_rank() OVER (ORDER BY contracted_value DESC NULLS LAST) AS contracted_rank
    FROM contracted;

CREATE OR REPLACE MACRO metric_contract_expiry(
    p_suppliers := NULL::VARCHAR[], p_categories := NULL::VARCHAR[]
) AS TABLE
    WITH expiry AS (
        SELECT c.*, ctx.as_of_date,
               date_diff('day', ctx.as_of_date, c.validity_end_date) AS days_to_expiry
        FROM _metric_contract_scope(p_suppliers, p_categories) AS c
        CROSS JOIN analytics_run_context AS ctx
    )
    SELECT *,
           CASE WHEN days_to_expiry < 0 THEN 'expired'
                WHEN days_to_expiry <= 30 THEN 'expires_in_30_days'
                WHEN days_to_expiry <= 60 THEN 'expires_in_60_days'
                WHEN days_to_expiry <= 90 THEN 'expires_in_90_days'
                WHEN days_to_expiry > 90 THEN 'outside_renewal_window'
           END AS expiry_status,
           coalesce(contract_status = 'ativo' AND days_to_expiry BETWEEN 0 AND 90, false)
               AS is_active_expiring_in_90_days
    FROM expiry;

CREATE OR REPLACE MACRO metric_contract_snapshot(
    p_suppliers := NULL::VARCHAR[], p_categories := NULL::VARCHAR[]
) AS TABLE
    SELECT count(*) AS contract_count,
           count(*) FILTER (contract_status = 'ativo') AS active_contract_count,
           count(*) FILTER (contract_status = 'vencido') AS expired_contract_count,
           count(*) FILTER (contract_status = 'encerrado') AS closed_contract_count,
           count(*) FILTER (is_active_expiring_in_90_days) AS active_expiring_in_90_days_count,
           sum(total_value) AS contracted_value,
           sum(balance_value) AS balance_value,
           sum(total_value - balance_value) AS consumed_value,
           sum(total_value - balance_value) / nullif(sum(total_value), 0) AS consumption_ratio
    FROM metric_contract_expiry(p_suppliers, p_categories);

CREATE OR REPLACE MACRO metric_spending_payments(
    p_start := NULL::DATE, p_end := NULL::DATE,
    p_suppliers := NULL::VARCHAR[], p_categories := NULL::VARCHAR[]
) AS TABLE
    SELECT s.* REPLACE (
        c.supplier_key AS supplier_key, c.supplier_legal_name AS supplier_legal_name,
        c.economic_group_key AS economic_group_key, c.category_key AS category_key,
        c.category_code AS category_code, c.category_name AS category_name,
        c.category_macro_group AS category_macro_group, c.category_group AS category_group,
        c.category_family AS category_family
    )
    FROM vw_spending AS s
    JOIN _metric_contract_scope(p_suppliers, p_categories) AS c USING (contract_key)
    WHERE s.payment_date IS NOT NULL
      AND (p_start IS NULL OR s.payment_date >= p_start::DATE)
      AND (p_end IS NULL OR s.payment_date <= p_end::DATE);

CREATE OR REPLACE MACRO metric_spending(
    p_start := NULL::DATE, p_end := NULL::DATE,
    p_suppliers := NULL::VARCHAR[], p_categories := NULL::VARCHAR[]
) AS TABLE
    WITH totals AS (
        SELECT economic_group_key, supplier_key, supplier_legal_name,
               count(*) AS payment_count, sum(payment_value) AS total_spending
        FROM metric_spending_payments(p_start, p_end, p_suppliers, p_categories)
        GROUP BY economic_group_key, supplier_key, supplier_legal_name
    )
    SELECT *,
           total_spending / nullif(sum(total_spending) OVER (), 0) AS spending_concentration_ratio,
           dense_rank() OVER (ORDER BY total_spending DESC NULLS LAST) AS spending_rank
    FROM totals;
