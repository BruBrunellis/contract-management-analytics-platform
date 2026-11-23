from datetime import date
from decimal import Decimal

import duckdb
import pytest
from conftest import PROJECT_ROOT

SQL_DIR = PROJECT_ROOT / "2.src" / "4.analytics" / "sql"


@pytest.fixture
def banco():
    with duckdb.connect() as conexao:
        conexao.execute(
            """
            CREATE TABLE analytics_run_context(as_of_date DATE);
            INSERT INTO analytics_run_context VALUES (DATE '2026-07-31');
            CREATE TABLE vw_contracts (
                contract_key VARCHAR, supplier_key VARCHAR, category_key VARCHAR,
                validity_start_date DATE, validity_end_date DATE, risk_evaluation_date DATE,
                contract_type VARCHAR, contract_status VARCHAR, final_risk VARCHAR,
                original_value DECIMAL(18,2), total_value DECIMAL(18,2), balance_value DECIMAL(18,2),
                supplier_legal_name VARCHAR, economic_group_key VARCHAR, category_code VARCHAR,
                category_name VARCHAR, category_macro_group VARCHAR, category_group VARCHAR,
                category_family VARCHAR
            );
            CREATE TABLE vw_renewals (
                contract_key VARCHAR, validity_start_date DATE, amendment_type VARCHAR,
                amendment_value DECIMAL(18,2)
            );
            CREATE TABLE vw_spending (
                payment_id VARCHAR, contract_key VARCHAR, payment_date DATE,
                payment_value DECIMAL(18,2), supplier_key VARCHAR, supplier_legal_name VARCHAR,
                economic_group_key VARCHAR, category_key VARCHAR, category_code VARCHAR,
                category_name VARCHAR, category_macro_group VARCHAR, category_group VARCHAR,
                category_family VARCHAR
            );
            """
        )
        conexao.execute((SQL_DIR / "09_metric_temporal.sql").read_text(encoding="utf-8"))
        yield conexao


def test_posicao_fluxo_e_fechamento_por_data_e_por_contrato(banco):
    banco.execute(
        """
        INSERT INTO vw_contracts (contract_key, supplier_key, category_key, validity_start_date,
                                 contract_type, original_value, total_value, balance_value)
        VALUES ('C1', 'S1', 'A', '2024-12-31', 'novo_contrato', 1000, 1400, 1010),
               ('C2', 'S2', 'B', '2025-12-31', 'novo_contrato', 400, 400, 365);
        INSERT INTO vw_renewals VALUES
            ('C1', '2025-01-01', 'renovacao', 200),
            ('C1', '2025-12-31', 'renovacao', 40),
            ('C1', '2025-12-31', 'aporte', 100),
            ('C1', '2026-01-01', 'aporte', 60);
        INSERT INTO vw_spending (payment_id, contract_key, payment_date, payment_value)
        VALUES ('P1', 'C1', '2024-12-31', 100), ('P2', 'C1', '2025-01-01', 150),
               ('P3', 'C1', '2025-12-31', 50), ('P4', 'C2', '2025-12-31', 25),
               ('P5', 'C1', '2026-01-01', 40), ('P6', 'C2', '2026-07-31', 10);
        """
    )
    assert banco.execute(
        """
        SELECT contracted_value, paid_value, net_flow_value,
               new_contract_count, renewed_contract_count, renewal_event_count
        FROM metric_contract_annual_flow([2025])
        """
    ).fetchone() == (740, 225, 515, 1, 1, 2)
    assert banco.execute(
        """
        SELECT fiscal_year, contracted_value, paid_value, balance_value
        FROM metric_contract_year_close([2025, 2024, 2025])
        """
    ).fetchall() == [(2024, 1000, 100, 900), (2025, 1740, 325, 1415)]
    assert banco.execute(
        "SELECT contracted_value, paid_value, balance_value "
        "FROM metric_contract_position(DATE '2026-01-01')"
    ).fetchone() == (1800, 365, 1435)
    assert banco.execute(
        "SELECT balance_value FROM metric_contract_position(DATE '2026-07-31', ['S1'], ['A'])"
    ).fetchone() == (1060,)
    assert banco.execute(
        "SELECT balance_value FROM metric_contract_position(DATE '2026-07-31', [], NULL)"
    ).fetchone() == (None,)
    assert banco.execute(
        "SELECT contracted_value, renewed_contract_count FROM metric_contract_annual_flow()"
    ).fetchone() == (1800, 1)
    assert banco.execute(
        "SELECT supplier_key, contracted_rank FROM metric_annual_supplier_ranking([2025]) "
        "ORDER BY contracted_rank"
    ).fetchall() == [("S2", 1), ("S1", 2)]


def test_janela_movel_limites_inclusivos_e_base_positiva(banco):
    banco.execute(
        """
        INSERT INTO vw_contracts (contract_key, supplier_key, category_key,
                                 validity_start_date, original_value)
        VALUES ('X0', 'S', 'X', '2025-07-31', 900), ('X1', 'S', 'X', '2025-08-01', 100),
               ('X2', 'S', 'X', '2026-02-01', 80), ('Z0', 'S', 'Z', '2026-02-01', 100),
               ('Z1', 'S', 'Z', '2025-10-01', -50), ('Y1', 'S', 'Y', '2025-10-01', 0),
               ('N1', 'S', 'N', '2026-02-01', 100), ('W1', 'S', 'W', '2025-08-01', 100);
        INSERT INTO vw_renewals VALUES
            ('X1', '2026-01-31', 'renovacao', 50), ('X2', '2026-07-31', 'aporte', 120),
            ('X2', '2026-08-01', 'aporte', 900);
        """
    )
    row = banco.execute("SELECT * FROM metric_contract_rolling(6, NULL, ['X'])").fetchone()
    assert row[:6] == (date(2025, 8, 1), date(2026, 1, 31), date(2026, 2, 1), date(2026, 7, 31),
                       150, 200)
    assert row[6] == pytest.approx(1 / 3)
    assert banco.execute(
        "SELECT current_contracted_value FROM metric_contract_rolling(p_categories := ['X'])"
    ).fetchone() == (350,)
    for categoria in ["Z", "Y", "N"]:
        assert banco.execute(
            "SELECT growth_ratio FROM metric_contract_rolling(6, NULL, [?])", [categoria]
        ).fetchone() == (None,)
    assert banco.execute(
        "SELECT growth_ratio FROM metric_contract_rolling(6, NULL, ['W'])"
    ).fetchone() == (-1,)
    with pytest.raises(duckdb.InvalidInputException, match="janela"):
        banco.execute("SELECT * FROM metric_contract_rolling(3)").fetchall()


def test_filtro_de_gastos_usa_chaves_do_contrato_e_denominador_da_selecao(banco):
    banco.execute(
        """
        INSERT INTO vw_contracts (contract_key, supplier_key, category_key,
                                  supplier_legal_name, economic_group_key)
        VALUES ('C1', 'S1', 'A', 'Mesmo nome', 'G'), ('C2', 'S2', 'A', 'Mesmo nome', 'G'),
               ('C3', 'S1', 'B', 'Mesmo nome', 'G');
        INSERT INTO vw_spending (payment_id, contract_key, payment_date, payment_value,
                                 supplier_key, category_key)
        VALUES ('P0', 'C1', '2025-12-31', 99, 'S1', 'A'),
               ('P1', 'C1', '2026-01-01', 10, 'outro', 'B'),
               ('P2', 'C2', '2026-01-02', 30, 'S2', 'A'),
               ('P3', 'C3', '2026-01-02', 60, 'S1', 'B'),
               ('P4', 'C1', NULL, 99, 'S1', 'A');
        """
    )
    assert banco.execute(
        "SELECT supplier_key, total_spending, spending_concentration_ratio, spending_rank "
        "FROM metric_spending(DATE '2026-01-01', DATE '2026-01-02', NULL, ['A']) "
        "ORDER BY supplier_key"
    ).fetchall() == [("S1", 10, 0.25, 2), ("S2", 30, 0.75, 1)]
    assert banco.execute(
        "SELECT payment_id, category_key, supplier_key "
        "FROM metric_spending_payments(DATE '2026-01-01', DATE '2026-01-01')"
    ).fetchone() == ("P1", "A", "S1")


def test_vencimento_tem_faixa_por_data_e_alerta_apenas_para_ativos(banco):
    banco.execute(
        """
        INSERT INTO vw_contracts (
            contract_key, validity_end_date, risk_evaluation_date, contract_status, total_value
        )
        VALUES ('C0', '2026-07-30', NULL, 'vencido', 0),
               ('C1', '2026-07-31', NULL, 'ativo', 0),
               ('C2', '2026-10-29', NULL, 'ativo', 0),
               ('C3', '2026-10-30', NULL, 'ativo', 0),
               ('C4', '2026-07-31', '2025-12-31', 'encerrado', 0),
               ('C5', NULL, NULL, 'ativo', 0);
        """
    )
    assert banco.execute(
        "SELECT contract_key, days_to_expiry, expiry_status, is_active_expiring_in_90_days "
        "FROM metric_contract_expiry() ORDER BY contract_key"
    ).fetchall() == [
        ("C0", -1, "expired", False),
        ("C1", 0, "expires_in_30_days", True),
        ("C2", 90, "expires_in_90_days", True),
        ("C3", 91, "outside_renewal_window", False),
        ("C4", 0, "expires_in_30_days", False),
        ("C5", None, None, False),
    ]
    assert banco.execute(
        "SELECT active_expiring_in_90_days_count, consumption_ratio FROM metric_contract_snapshot()"
    ).fetchone() == (2, None)
    assert banco.execute(
        "SELECT expired_contract_count, closed_contract_count FROM metric_contract_annual_flow([2025])"
    ).fetchone() == (0, 1)


def test_posicao_preserva_valor_monetario_decimal(banco):
    banco.execute(
        """
        INSERT INTO vw_contracts (contract_key, validity_start_date, original_value)
        VALUES ('C', '2026-01-01', 0.30);
        INSERT INTO vw_spending (contract_key, payment_date, payment_value)
        VALUES ('C', '2026-01-01', 0.10);
        """
    )
    assert banco.execute(
        "SELECT balance_value FROM metric_contract_position(DATE '2026-01-01')"
    ).fetchone() == (Decimal("0.20"),)


@pytest.fixture
def banco_financeiro(banco):
    banco.execute(
        """
        CREATE TABLE vw_suppliers (
            supplier_key VARCHAR, supplier_cnpj VARCHAR, supplier_legal_name VARCHAR,
            supplier_hierarchy VARCHAR, parent_supplier_key VARCHAR, economic_group_key VARCHAR,
            financial_scenario VARCHAR
        );
        CREATE TABLE vw_rfi (
            supplier_key VARCHAR, assessment_date DATE, risk_assessment_id VARCHAR,
            homologation_status VARCHAR, final_risk VARCHAR
        );
        CREATE TABLE src_fact_supplier_financial (
            financial_snapshot_key VARCHAR, supplier_key VARCHAR, financial_year INTEGER,
            financial_period_calendar_key DATE, gross_revenue DECIMAL(18,2),
            total_cost DECIMAL(18,2), net_income DECIMAL(18,2), economic_group_key VARCHAR,
            payroll_cost DECIMAL(18,2), gross_profit DECIMAL(18,2), debt_interest DECIMAL(18,2)
        );
        CREATE VIEW src_dim_contract AS
            SELECT *, validity_start_date AS validity_start_calendar_key,
                   validity_end_date AS validity_end_calendar_key
            FROM vw_contracts;
        CREATE VIEW src_dim_calendar AS
            SELECT calendar_date AS calendar_key, calendar_date FROM (
                SELECT validity_start_date AS calendar_date FROM vw_contracts
                UNION SELECT validity_end_date FROM vw_contracts
                UNION SELECT financial_period_calendar_key FROM src_fact_supplier_financial
            );
        CREATE VIEW src_dim_supplier AS SELECT * FROM vw_suppliers;
        CREATE VIEW src_dim_economic_group AS
            SELECT DISTINCT economic_group_key, economic_group_key AS economic_group_legal_name
            FROM vw_suppliers;
        """
    )
    for arquivo in ("08_vw_supplier_financials.sql", "10_metric_financial_risk.sql"):
        banco.execute((SQL_DIR / arquivo).read_text(encoding="utf-8"))
    return banco


def test_exposicao_anual_dependencia_ativa_e_contexto_financeiro(banco_financeiro):
    banco = banco_financeiro
    banco.execute(
        """
        INSERT INTO vw_suppliers VALUES
            ('M', 'M-CNPJ', 'Matriz', 'Matriz', NULL, 'G', 'estavel'),
            ('F', 'F-CNPJ', 'Filial', 'Filial', 'M', 'G', 'estavel'),
            ('Z', 'Z-CNPJ', 'Zero', 'Matriz', NULL, 'Z', 'estavel'),
            ('N', 'N-CNPJ', 'Sem receita', 'Matriz', NULL, 'N', 'estavel'),
            ('P', 'P-CNPJ', 'Sem valor', 'Matriz', NULL, 'P', 'estavel');
        INSERT INTO vw_contracts (contract_key, supplier_key, category_key, category_name,
                                 contract_status, validity_start_date, validity_end_date, total_value)
        VALUES ('M0', 'M', 'A', 'A', 'encerrado', '2026-01-01', '2026-03-31', 90),
               ('M1', 'M', 'A', 'A', 'ativo', '2026-01-01', '2026-12-31', 365),
               ('M2', 'M', 'B', 'B', 'ativo', '2026-01-01', '2026-12-31', 730),
               ('F1', 'F', 'A', 'A', 'ativo', '2026-01-01', '2026-12-31', 365),
               ('Z1', 'Z', 'A', 'A', 'ativo', '2026-01-01', '2026-12-31', 365),
               ('N1', 'N', 'A', 'A', 'ativo', '2026-01-01', '2026-12-31', 365),
               ('P1', 'P', 'A', 'A', 'ativo', '2026-01-01', '2026-12-31', 0);
        INSERT INTO src_fact_supplier_financial (
            financial_snapshot_key, supplier_key, financial_year, financial_period_calendar_key,
            gross_revenue, total_cost, net_income, economic_group_key
        )
        VALUES ('M25', 'M', 2025, '2025-12-31', 5000, 4000, 500, 'G'),
               ('M26', 'M', 2026, '2026-12-31', 3652.50, 2500, 365.25, 'G'),
               ('F26', 'F', 2026, '2026-12-31', 1461, 1000, 292.20, 'G'),
               ('Z25', 'Z', 2025, '2025-12-31', 1000, 800, 20, 'Z'),
               ('Z26', 'Z', 2026, '2026-12-31', 0, 0, 0, 'Z'),
               ('P26', 'P', 2026, '2026-12-31', 1000, 0, 0, 'P');
        """
    )
    assert banco.execute(
        "SELECT annual_exposure_value, annual_dependency_ratio "
        "FROM metric_supplier_annual_exposure([2026], ['M'])"
    ).fetchone() == pytest.approx((1461, 0.40))
    assert banco.execute(
        "SELECT annualized_contract_value, financial_dependency_ratio "
        "FROM vw_supplier_financials WHERE supplier_key = 'M' AND financial_year = 2026"
    ).fetchone() == pytest.approx((1461, 0.40))
    rows = banco.execute(
        "SELECT supplier_key, active_contract_count, active_annualized_value, "
        "latest_revenue_period_end_date, active_dependency_ratio, active_revenue_coverage_ratio "
        "FROM metric_supplier_active_dependency()"
    ).fetchall()
    data = {supplier: values for supplier, *values in rows}
    assert data["M"] == [2, 1095.75, date(2026, 12, 31), 0.30, pytest.approx(10 / 3)]
    assert data["F"] == [1, 365.25, date(2026, 12, 31), 0.25, 4]
    assert data["Z"] == [1, 365.25, date(2026, 12, 31), None, 0]
    assert data["N"] == [1, 365.25, None, None, None]
    assert data["P"] == [1, 0, date(2026, 12, 31), 0, None]
    category_rows = banco.execute(
        "SELECT category_key, is_total, eligible_contract_count, weighted_dependency_ratio "
        "FROM metric_category_active_dependency() ORDER BY is_total, category_key"
    ).fetchall()
    assert category_rows == [
        ("A", False, 2, pytest.approx(0.275)),
        ("B", False, 1, pytest.approx(0.30)),
        (None, True, 3, pytest.approx(0.2875)),
    ]
    assert banco.execute(
        "SELECT weighted_dependency_ratio "
        "FROM metric_category_active_dependency(['M'], ['A']) WHERE is_total"
    ).fetchone() == (pytest.approx(0.30),)
    assert banco.execute(
        "SELECT eligible_contract_count, weighted_dependency_ratio "
        "FROM metric_category_active_dependency(['Z', 'N'], ['A']) WHERE is_total"
    ).fetchone() == (0, None)
    assert banco.execute(
        "SELECT active_supplier_count FROM metric_supplier_financial_scenarios()"
    ).fetchone() == (5,)
    history = banco.execute(
        "SELECT gross_revenue, total_cost, net_income, net_margin "
        "FROM metric_supplier_financial_history([2026], NULL, ['A'])"
    ).fetchone()
    assert history[:3] == (Decimal("5113.50"), 3500, Decimal("657.45"))
    assert history[3] == pytest.approx(657.45 / 5113.5)


def test_carteira_ativa_aceita_um_dia_e_exclui_datas_invalidas(banco_financeiro):
    banco = banco_financeiro
    banco.execute(
        """
        INSERT INTO vw_suppliers (supplier_key) VALUES ('S');
        INSERT INTO vw_contracts (contract_key, supplier_key, contract_status, validity_start_date,
                                 validity_end_date, total_value)
        VALUES ('hoje', 'S', 'ativo', '2026-07-31', '2026-07-31', 1),
               ('invertido', 'S', 'ativo', '2026-07-31', '2026-07-01', 1),
               ('sem_inicio', 'S', 'ativo', NULL, '2026-07-31', 1),
               ('amanha', 'S', 'ativo', '2026-08-01', '2026-12-31', 1);
        """
    )
    assert banco.execute(
        "SELECT active_contract_count, active_annualized_value "
        "FROM metric_supplier_active_dependency(['S'])"
    ).fetchone() == (1, 365.25)


def test_homologacao_desempata_por_id_e_exposicao_preserva_grao_de_evento(banco_financeiro):
    banco = banco_financeiro
    banco.execute(
        """
        INSERT INTO vw_rfi VALUES
            ('M', '2026-07-10', 'AV-01', 'pendente', 'alto'),
            ('M', '2026-07-10', 'AV-02', 'aprovado', 'baixo'),
            ('F', '2026-07-01', 'AV-03', 'aprovado', 'baixo'),
            ('F', '2026-07-10', 'AV-04', 'aprovado', 'alto');
        INSERT INTO vw_contracts (contract_key, supplier_key, category_key, validity_start_date,
                                 original_value)
        VALUES ('C0', 'F', 'A', '2025-07-31', 900), ('C1', 'M', 'A', '2025-08-01', 100),
               ('C2', 'F', 'A', '2026-07-31', 80), ('C3', 'N', 'A', '2026-07-31', 20);
        INSERT INTO vw_renewals VALUES ('C2', '2026-07-31', 'aporte', 20);
        """
    )
    assert banco.execute(
        "SELECT risk_assessment_id, homologation_status, final_risk "
        "FROM metric_supplier_latest_rfi(['M'])"
    ).fetchone() == ("AV-02", "aprovado", "baixo")
    assert banco.execute("SELECT * FROM metric_supplier_latest_rfi(['N'])").fetchone() is None
    assert banco.execute(
        "SELECT * FROM metric_high_risk_exposure(p_categories := ['A'])"
    ).fetchone() == pytest.approx((220, 100, 100 / 220))


def test_risco_de_aporte_conserva_limites_inclusivos_e_bases_ausentes(banco_financeiro):
    banco = banco_financeiro
    banco.execute(
        """
        INSERT INTO vw_contracts (
            contract_key, contract_status, validity_start_date, validity_end_date,
            total_value, balance_value
        )
        SELECT 'C' || id::VARCHAR, status, DATE '2026-07-31' - days_elapsed,
               DATE '2026-07-31' + days_left, total, balance
        FROM (VALUES (1, 'ativo', 50, 50, 1000, 300), (2, 'ativo', 50, 50, 1000, 450),
                     (3, 'ativo', 50, 50, 1000, 451), (4, 'ativo', 50, 50, 0, 0),
                     (5, 'ativo', 0, 0, 1000, 500), (6, 'ativo', 50, 50, 1000, NULL),
                     (7, 'encerrado', 50, 50, 1000, 450))
             AS examples(id, status, days_elapsed, days_left, total, balance);
        """
    )
    assert banco.execute(
        "SELECT contract_key, funding_risk FROM metric_contract_funding_risk() "
        "ORDER BY contract_key"
    ).fetchall() == [
        ("C1", "Alto"), ("C2", "Médio"), ("C3", "Baixo"),
        ("C4", None), ("C5", None), ("C6", None),
    ]


def test_risco_por_categoria_recalcula_o_total_e_desempata_extremos(banco_financeiro):
    banco = banco_financeiro
    banco.execute(
        """
        INSERT INTO vw_contracts (contract_key, category_key, category_name,
                                 final_risk, balance_value)
        VALUES ('C1', 'A', 'Zulu', 'alto', 100), ('C2', 'A', 'Zulu', NULL, 100),
               ('C3', 'B', 'Alfa', 'medio', 300), ('C4', 'C', 'Beta', 'baixo', 100),
               ('C5', 'D', 'Gama', NULL, 200), ('C6', 'E', 'Zero', 'alto', 0);
        """
    )
    assert banco.execute(
        "SELECT weighted_risk FROM metric_category_risk() WHERE is_total"
    ).fetchone() == (pytest.approx(260 / 800),)
    assert banco.execute(
        "SELECT weighted_risk FROM metric_category_risk(p_categories := ['D']) WHERE NOT is_total"
    ).fetchone() == (None,)
    assert banco.execute("SELECT * FROM metric_category_risk_extremes()").fetchone() == (
        0.5, "B", "Alfa", 0.1, "C", "Beta",
    )
