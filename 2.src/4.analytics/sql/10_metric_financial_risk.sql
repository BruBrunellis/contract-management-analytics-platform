CREATE OR REPLACE MACRO metric_supplier_annual_exposure(
    p_years := NULL::INTEGER[], p_suppliers := NULL::VARCHAR[]
) AS TABLE
    SELECT supplier_key, supplier_cnpj, supplier_legal_name, economic_group_key,
           financial_year, financial_period_end_date, gross_revenue,
           annualized_contract_value AS annual_exposure_value,
           financial_dependency_ratio AS annual_dependency_ratio,
           revenue_to_contract_coverage_ratio AS annual_revenue_coverage_ratio
    FROM vw_supplier_financials AS f
    WHERE (p_years IS NULL OR list_contains(p_years::INTEGER[], f.financial_year))
      AND (p_suppliers IS NULL OR list_contains(p_suppliers::VARCHAR[], f.supplier_key));

CREATE OR REPLACE MACRO _metric_active_contracts(p_suppliers, p_categories) AS TABLE
    SELECT c.*, ctx.as_of_date,
           c.total_value * 365.25 / (date_diff('day', validity_start_date, validity_end_date) + 1)
               AS active_annualized_value
    FROM _metric_contract_scope(p_suppliers, p_categories) AS c
    CROSS JOIN analytics_run_context AS ctx
    WHERE c.contract_status = 'ativo'
      AND ctx.as_of_date BETWEEN c.validity_start_date AND c.validity_end_date;

CREATE OR REPLACE MACRO metric_supplier_active_dependency(
    p_suppliers := NULL::VARCHAR[]
) AS TABLE
    WITH portfolio AS (
        SELECT supplier_key, as_of_date, count(*) AS active_contract_count,
               sum(active_annualized_value) AS active_annualized_value
        FROM _metric_active_contracts(p_suppliers, NULL)
        GROUP BY supplier_key, as_of_date
    ),
    latest_revenue AS (
        SELECT f.supplier_key, f.financial_period_end_date, f.gross_revenue
        FROM vw_supplier_financials AS f
        JOIN portfolio AS p ON p.supplier_key = f.supplier_key
        WHERE f.financial_period_end_date IS NOT NULL
        QUALIFY row_number() OVER (
            PARTITION BY f.supplier_key
            ORDER BY f.financial_period_end_date DESC, f.financial_snapshot_key DESC NULLS LAST
        ) = 1
    )
    SELECT p.*, s.supplier_cnpj, s.supplier_legal_name, s.supplier_hierarchy,
           s.parent_supplier_key, s.economic_group_key, s.financial_scenario,
           r.financial_period_end_date AS latest_revenue_period_end_date,
           r.gross_revenue AS latest_gross_revenue,
           p.active_annualized_value / nullif(r.gross_revenue, 0) AS active_dependency_ratio,
           r.gross_revenue / nullif(p.active_annualized_value, 0) AS active_revenue_coverage_ratio
    FROM portfolio AS p
    JOIN vw_suppliers AS s ON s.supplier_key = p.supplier_key
    LEFT JOIN latest_revenue AS r ON r.supplier_key = p.supplier_key;

CREATE OR REPLACE MACRO metric_category_active_dependency(
    p_suppliers := NULL::VARCHAR[], p_categories := NULL::VARCHAR[]
) AS TABLE
    WITH weights AS (
        SELECT c.category_key, c.category_name, c.active_annualized_value AS contract_weight,
               d.active_dependency_ratio,
               c.active_annualized_value > 0 AND d.active_dependency_ratio IS NOT NULL AS eligible
        FROM _metric_active_contracts(p_suppliers, p_categories) AS c
        JOIN metric_supplier_active_dependency(p_suppliers) AS d USING (supplier_key)
    )
    SELECT category_key, category_name, grouping(category_key) = 1 AS is_total,
           count(*) FILTER (eligible) AS eligible_contract_count,
           sum(contract_weight) FILTER (eligible) AS annualized_weight,
           (sum(contract_weight * active_dependency_ratio) FILTER (eligible))
               / nullif(sum(contract_weight) FILTER (eligible), 0) AS weighted_dependency_ratio
    FROM weights
    GROUP BY GROUPING SETS ((category_key, category_name), ());

CREATE OR REPLACE MACRO metric_supplier_financial_scenarios(
    p_suppliers := NULL::VARCHAR[], p_categories := NULL::VARCHAR[]
) AS TABLE
    WITH active_suppliers AS (
        SELECT DISTINCT supplier_key FROM _metric_active_contracts(p_suppliers, p_categories)
    )
    SELECT s.financial_scenario, count(*) AS active_supplier_count
    FROM active_suppliers
    JOIN vw_suppliers AS s USING (supplier_key)
    GROUP BY s.financial_scenario;

CREATE OR REPLACE MACRO metric_supplier_financial_history(
    p_years := NULL::INTEGER[], p_suppliers := NULL::VARCHAR[], p_categories := NULL::VARCHAR[]
) AS TABLE
    WITH active_suppliers AS (
        SELECT supplier_key
        FROM _metric_active_contracts(p_suppliers, p_categories)
        GROUP BY supplier_key
        HAVING sum(active_annualized_value) > 0
    )
    SELECT f.financial_year,
           sum(f.gross_revenue) AS gross_revenue, sum(f.total_cost) AS total_cost,
           sum(f.net_income) AS net_income,
           sum(f.net_income) / nullif(sum(f.gross_revenue), 0) AS net_margin
    FROM vw_supplier_financials AS f
    JOIN active_suppliers AS a USING (supplier_key)
    WHERE p_years IS NULL OR list_contains(p_years::INTEGER[], f.financial_year)
    GROUP BY f.financial_year;

CREATE OR REPLACE MACRO metric_supplier_latest_rfi(p_suppliers := NULL::VARCHAR[]) AS TABLE
    SELECT r.*
    FROM vw_rfi AS r
    WHERE p_suppliers IS NULL OR list_contains(p_suppliers::VARCHAR[], r.supplier_key)
    QUALIFY row_number() OVER (
        PARTITION BY r.supplier_key
        ORDER BY r.assessment_date DESC NULLS LAST, r.risk_assessment_id DESC NULLS LAST
    ) = 1;

CREATE OR REPLACE MACRO metric_category_risk(
    p_suppliers := NULL::VARCHAR[], p_categories := NULL::VARCHAR[]
) AS TABLE
    WITH contracts AS (
        SELECT category_key, category_name, balance_value, final_risk,
               CASE final_risk WHEN 'alto' THEN 1.0 WHEN 'medio' THEN 0.5 WHEN 'baixo' THEN 0.1
               END AS risk_weight
        FROM _metric_contract_scope(p_suppliers, p_categories)
    )
    SELECT category_key, category_name, grouping(category_key) = 1 AS is_total,
           count(*) FILTER (final_risk = 'alto') AS high_risk_contract_count,
           count(*) FILTER (final_risk = 'medio') AS medium_risk_contract_count,
           count(*) FILTER (final_risk = 'baixo') AS low_risk_contract_count,
           (sum(balance_value * risk_weight) FILTER (balance_value > 0))
               / nullif(sum(balance_value) FILTER (balance_value > 0), 0) AS weighted_risk
    FROM contracts
    GROUP BY GROUPING SETS ((category_key, category_name), ());

CREATE OR REPLACE MACRO metric_category_risk_extremes(
    p_suppliers := NULL::VARCHAR[], p_categories := NULL::VARCHAR[]
) AS TABLE
    SELECT max(weighted_risk) AS highest_weighted_risk,
           first(category_key ORDER BY weighted_risk DESC, category_name, category_key)
               AS highest_risk_category_key,
           first(category_name ORDER BY weighted_risk DESC, category_name, category_key)
               AS highest_risk_category_name,
           min(weighted_risk) AS lowest_weighted_risk,
           first(category_key ORDER BY weighted_risk ASC, category_name, category_key)
               AS lowest_risk_category_key,
           first(category_name ORDER BY weighted_risk ASC, category_name, category_key)
               AS lowest_risk_category_name
    FROM metric_category_risk(p_suppliers, p_categories)
    WHERE NOT is_total AND weighted_risk IS NOT NULL;

CREATE OR REPLACE MACRO metric_contract_funding_risk(
    p_suppliers := NULL::VARCHAR[], p_categories := NULL::VARCHAR[]
) AS TABLE
    WITH duration AS (
        SELECT c.contract_key, c.supplier_key, c.category_key, c.contract_status,
               c.total_value, c.balance_value, ctx.as_of_date,
               date_diff('day', c.validity_start_date, c.validity_end_date) AS duration_days,
               date_diff('day', c.validity_start_date, ctx.as_of_date) AS days_from_start
        FROM _metric_contract_scope(p_suppliers, p_categories) AS c
        CROSS JOIN analytics_run_context AS ctx
        WHERE c.contract_status = 'ativo'
    ),
    fractions AS (
        SELECT *, (total_value - balance_value) / nullif(total_value, 0) AS consumption_ratio,
               CASE WHEN duration_days > 0 THEN least(greatest(days_from_start, 0), duration_days)
               END AS elapsed_days
        FROM duration
    ),
    scaled AS (
        SELECT *, elapsed_days / nullif(duration_days, 0) AS elapsed_validity_ratio,
               (total_value - balance_value) * sign(total_value) * duration_days
                   - elapsed_days * abs(total_value) AS scaled_deviation,
               abs(total_value) * duration_days AS deviation_scale
        FROM fractions
    )
    SELECT contract_key, supplier_key, category_key, contract_status, as_of_date,
           balance_value / nullif(total_value, 0) AS balance_ratio,
           consumption_ratio, elapsed_validity_ratio,
           consumption_ratio - elapsed_validity_ratio AS funding_deviation,
           CASE WHEN consumption_ratio IS NULL OR elapsed_validity_ratio IS NULL THEN NULL
                -- Compare com a mesma base para manter inclusivos os limiares de 20 e 5 p.p.
                WHEN scaled_deviation >= 0.20 * deviation_scale THEN 'Alto'
                WHEN scaled_deviation >= 0.05 * deviation_scale THEN 'Médio'
                ELSE 'Baixo'
           END AS funding_risk
    FROM scaled;

CREATE OR REPLACE MACRO metric_high_risk_exposure(
    p_suppliers := NULL::VARCHAR[], p_categories := NULL::VARCHAR[]
) AS TABLE
    WITH exposure AS (
        SELECT sum(e.event_value) AS contracted_12m,
               sum(e.event_value) FILTER (r.final_risk = 'alto') AS high_risk_contracted_12m
        FROM _metric_events(p_suppliers, p_categories) AS e
        CROSS JOIN analytics_run_context AS ctx
        LEFT JOIN metric_supplier_latest_rfi(p_suppliers) AS r ON e.supplier_key = r.supplier_key
        WHERE e.event_kind <> 'payment'
          AND e.event_date > (ctx.as_of_date - INTERVAL 12 MONTH)::DATE
          AND e.event_date <= ctx.as_of_date
    )
    SELECT *, high_risk_contracted_12m / nullif(contracted_12m, 0) AS high_risk_exposure_ratio
    FROM exposure;
