import random
from datetime import date

from conftest import load_module


def test_spending_de_contratos_vencidos_concilia_com_saldo():
    random.seed(42)
    empresas = load_module("company_generator.py").gerar_tabela_empresas(qtd=50)
    riscos = load_module("risk_generator.py").gerar_homologacoes_risco(empresas, date(2026, 7, 30))
    contratos, aditamentos = load_module("contract_generator.py").gerar_tabelas_contratos(
        empresas, riscos, date(2026, 7, 30)
    )
    spending = load_module("spending_generator.py").gerar_tabela_spending(
        contratos, aditamentos, date(2026, 7, 30), date(2026, 7, 30)
    )
    totais = spending.groupby("Cód_Contrato")["Valor_Pago"].sum()
    vencidos = contratos[contratos["Status"].eq("Vencido")].set_index("Cód_Contrato")

    assert spending["Cód_Pagamento"].is_unique
    assert (spending["Valor_Pago"] > 0).all()
    assert {"Centro_Custo", "Categoria"}.issubset(spending.columns)
    assert spending["Centro_Custo"].str.fullmatch(r"CC-\d{3}").all()
    assert (
        totais.reindex(vencidos.index, fill_value=0).round(2)
        == (vencidos["Valor_Total"] - vencidos["Saldo"]).round(2)
    ).all()
