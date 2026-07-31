import random

from conftest import load_module


def test_empresas_possuem_relacoes_financeiras_e_hierarquicas_coerentes():
    random.seed(42)
    generator = load_module("company_generator.py")
    empresas = generator.gerar_tabela_empresas(qtd=40)
    matrizes = empresas[empresas["Hierarquia"].eq("Matriz")].set_index("CNPJ")
    filiais = empresas[empresas["Hierarquia"].eq("Filial")].join(
        matrizes[["Faturamento_2026", "Num_Total_Func"]],
        on="CNPJ_Matriz",
        rsuffix="_matriz",
    )

    assert len(matrizes) == 40
    assert empresas["CNPJ"].is_unique
    assert (empresas["Num_Func_CLT"] + empresas["Num_Func_PJ"]).eq(empresas["Num_Total_Func"]).all()
    assert (empresas["Custo_Folha_2026"] <= empresas["Custo_2026"]).all()
    assert (empresas["Custo_2026"] <= empresas["Faturamento_2026"]).all()
    assert (filiais["Faturamento_2026"] <= filiais["Faturamento_2026_matriz"]).all()
    assert (filiais["Num_Total_Func"] <= filiais["Num_Total_Func_matriz"]).all()
