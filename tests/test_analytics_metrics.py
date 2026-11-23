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


def test_posicao_preserva_valor_moneterio_decimal(banco):
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
