from datetime import date

import pandas as pd
import pyarrow.parquet as pq
from conftest import load_staging_module


def criar_homologacoes_risco():
    return pd.DataFrame(
        [
            {
                "Id_Avaliacao_Risco": "RSK000000001",
                "CNPJ": "13.241.241/0001-55",
                "Data_Avaliacao": "2026-01-01",
                "Data_Ultima_Homologacao": "2026-01-01",
                "Data_Expiracao": "2029-12-31",
                "Resultado_Homologacao": "Aprovada",
                "Status_Homologacao": "Ativa",
                "Risco_Financeiro": "Baixo",
                "Risco_Trabalhista": "Médio",
                "Rating_Credito": "AA",
                "Risco_Final": "Médio",
                "Indice_Juros_Sobre_Receita": 0.02,
                "Tendencia_Faturamento": 0.04,
                "Margem_Liquida": 0.10,
                "Indice_Processos_Trabalhistas": 1.2,
            }
        ]
    )


def test_staging_homologacoes_risco_padroniza_linhagem_e_score(tmp_path):
    origem = tmp_path / "homologacoes_risco_20260730_120000.csv"
    criar_homologacoes_risco().to_csv(origem, index=False, encoding="utf-8-sig")
    staging = load_staging_module("stg_homologacoes_risco.py")

    preparado = staging.preparar_dataframe(origem, date(2026, 7, 30))
    erros = staging.validar_homologacoes_risco(preparado, date(2026, 7, 30))

    assert erros.eq("").all()
    assert preparado.loc[0, "supplier_cnpj8"] == "13241241"
    assert preparado.loc[0, "homologation_status"] == "ativa"
    assert preparado.loc[0, "final_risk"] == "medio"
    assert preparado.loc[0, "batch_id"] == "20260730_120000"


def test_staging_homologacoes_risco_separa_cnpj_e_combinacao_invalidos(tmp_path):
    origem = tmp_path / "homologacoes_risco_20260730_120000.csv"
    homologacoes = criar_homologacoes_risco()
    homologacoes.loc[1] = homologacoes.loc[0]
    homologacoes.loc[1, "Id_Avaliacao_Risco"] = "RSK000000002"
    homologacoes.loc[1, "CNPJ"] = "invalido"
    homologacoes.loc[1, "Status_Homologacao"] = "Negada"
    homologacoes.loc[1, "Risco_Final"] = "Alto"
    homologacoes.to_csv(origem, index=False, encoding="utf-8-sig")
    staging = load_staging_module("stg_homologacoes_risco.py")

    resultado = staging.executar_staging(
        origem,
        "20260730_120000",
        date(2026, 7, 30),
        tmp_path / "staging",
        tmp_path / "staging" / "exceptions",
    )

    assert resultado["registros_validos"] == 1
    assert resultado["registros_invalidos"] == 1
    assert str(pq.read_schema(resultado["arquivo_staging"]).field("assessment_date").type) == "date32[day]"
    excecoes = pd.read_parquet(resultado["arquivo_excecoes"])
    assert "supplier_cnpj deve conter 14 dígitos" in excecoes.loc[0, "validation_errors"]
    assert "homologação aprovada com status inválido" in excecoes.loc[0, "validation_errors"]
    assert "homologação aprovada com risco final alto" in excecoes.loc[0, "validation_errors"]


def test_staging_homologacoes_risco_marca_id_duplicado(tmp_path):
    origem = tmp_path / "homologacoes_risco_20260730_120000.csv"
    homologacoes = criar_homologacoes_risco()
    homologacoes.loc[1] = homologacoes.loc[0]
    homologacoes.to_csv(origem, index=False, encoding="utf-8-sig")
    staging = load_staging_module("stg_homologacoes_risco.py")

    erros = staging.validar_homologacoes_risco(
        staging.preparar_dataframe(origem, date(2026, 7, 30)),
        date(2026, 7, 30),
    )

    assert erros.str.contains("risk_assessment_id duplicado").all()
