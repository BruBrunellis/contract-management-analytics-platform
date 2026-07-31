import random
from datetime import date

import pandas as pd
from conftest import load_module


def test_contratos_ativos_possuem_risco_aprovado_e_encerrados_risco_alto():
    random.seed(42)
    empresas = load_module("company_generator.py").gerar_tabela_empresas(qtd=50)
    riscos = load_module("risk_generator.py").gerar_homologacoes_risco(empresas, date(2026, 7, 30))
    contratos, _ = load_module("contract_generator.py").gerar_tabelas_contratos(
        empresas, riscos, date(2026, 7, 30)
    )
    riscos_atuais = riscos[riscos["Data_Avaliacao"].str.startswith("2026")][
        ["CNPJ", "Resultado_Homologacao", "Risco_Final"]
    ]
    ativos = contratos[contratos["Status"].eq("Ativo")].merge(riscos_atuais, on="CNPJ")
    encerrados = contratos[contratos["Status"].eq("Encerrado")]

    assert not contratos.empty
    assert (ativos["Resultado_Homologacao"].eq("Aprovada") & ativos["Risco_Final_y"].ne("Alto")).all()
    assert encerrados.empty or encerrados["Risco_Final"].eq("Alto").all()


def test_valor_original_usa_faturamento_do_ano_de_inicio_e_respeita_exposicao():
    random.seed(42)
    company_generator = load_module("company_generator.py")
    contract_generator = load_module("contract_generator.py")
    empresas = company_generator.gerar_tabela_empresas(qtd=50)
    riscos = load_module("risk_generator.py").gerar_homologacoes_risco(empresas, date(2026, 7, 30))
    contratos, _ = contract_generator.gerar_tabelas_contratos(
        empresas,
        riscos,
        date(2026, 7, 30),
        probabilidade_outlier_qtd_contratos=1.0,
    )

    empresa = empresas.iloc[0]
    assert contract_generator.faturamento_base_contrato(empresa, date(2021, 12, 31))[0] == float(
        empresa["Faturamento_2022"]
    )
    assert contract_generator.faturamento_base_contrato(empresa, date(2025, 1, 1))[0] == float(
        empresa["Faturamento_2025"]
    )
    assert contract_generator.quantidade_contratos("Grande", "Matriz", 1.0) in range(6, 13)

    contratos["ano_inicio"] = pd.to_datetime(contratos["Vigência Inicio"]).dt.year
    exposicao = contratos.groupby(["CNPJ", "ano_inicio"])["Valor_Original"].sum().reset_index()
    exposicao = exposicao.merge(empresas, on="CNPJ")
    for _, registro in exposicao.iterrows():
        faturamento = registro[f"Faturamento_{registro['ano_inicio']}"]
        assert registro["Valor_Original"] <= faturamento * 0.90 + 0.01
