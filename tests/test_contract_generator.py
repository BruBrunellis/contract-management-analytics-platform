import random
from datetime import date

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
