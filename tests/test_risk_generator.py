import random
from datetime import date

from conftest import load_module


def test_homologacao_ativa_nunca_tem_risco_final_alto():
    random.seed(42)
    empresas = load_module("company_generator.py").gerar_tabela_empresas(qtd=30)
    riscos = load_module("risk_generator.py").gerar_homologacoes_risco(empresas, date(2026, 7, 30))

    assert len(riscos) == len(empresas) * 5
    assert riscos["Id_Avaliacao_Risco"].is_unique
    assert not (riscos["Status_Homologacao"].eq("Ativa") & riscos["Risco_Final"].eq("Alto")).any()
    assert riscos.loc[riscos["Risco_Final"].eq("Alto"), "Resultado_Homologacao"].eq("Reprovada").all()
