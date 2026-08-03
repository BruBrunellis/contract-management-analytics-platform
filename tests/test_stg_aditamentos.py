from datetime import date

import pandas as pd
import pyarrow.parquet as pq
from conftest import load_staging_module


def criar_aditamentos():
    return pd.DataFrame(
        [
            {
                "Cód_Contrato": "CS00000001",
                "Tipo_Aditamento": "Renovação",
                "Vigência_Inicio": "2026-01-01",
                "Vigência_Fim": "2026-12-31",
                "Valor": 1200.50,
                "Sequencia_Aditamento": 1,
            },
            {
                "Cód_Contrato": "CS00000001",
                "Tipo_Aditamento": "Aporte",
                "Vigência_Inicio": "2026-06-01",
                "Vigência_Fim": "2026-12-31",
                "Valor": 300.00,
                "Sequencia_Aditamento": 2,
            },
        ]
    )


def criar_stg_contratos(tmp_path):
    arquivo = tmp_path / "stg_contratos_20260730_120000.parquet"
    pd.DataFrame({"contract_id": ["CS00000001"]}).to_parquet(arquivo, index=False)
    return arquivo


def test_staging_aditamentos_padroniza_ids_e_valida_referencia(tmp_path):
    origem = tmp_path / "aditamentos_20260730_120000.csv"
    criar_aditamentos().to_csv(origem, index=False, encoding="utf-8-sig")
    staging = load_staging_module("stg_aditamentos.py")

    preparado = staging.preparar_dataframe(origem, date(2026, 7, 30))
    erros = staging.validar_aditamentos(preparado, {"CS00000001"})

    assert erros.eq("").all()
    assert preparado.loc[0, "amendment_id"] == "AMD-CS00000001-0001"
    assert preparado.loc[0, "amendment_type"] == "renovacao"
    assert preparado.loc[0, "batch_id"] == "20260730_120000"


def test_staging_aditamentos_separa_contrato_ausente_e_dados_invalidos(tmp_path):
    origem = tmp_path / "aditamentos_20260730_120000.csv"
    aditamentos = criar_aditamentos().iloc[:1].copy()
    aditamentos.loc[0, "Cód_Contrato"] = "CS99999999"
    aditamentos.loc[0, "Vigência_Inicio"] = "2026-12-31"
    aditamentos.loc[0, "Vigência_Fim"] = "2026-01-01"
    aditamentos.loc[0, "Valor"] = 0
    aditamentos.to_csv(origem, index=False, encoding="utf-8-sig")
    staging = load_staging_module("stg_aditamentos.py")

    resultado = staging.executar_staging(
        origem,
        "20260730_120000",
        date(2026, 7, 30),
        tmp_path / "staging",
        tmp_path / "staging" / "exceptions",
        criar_stg_contratos(tmp_path),
    )

    assert resultado["registros_validos"] == 0
    assert resultado["registros_invalidos"] == 1
    excecoes = pd.read_parquet(resultado["arquivo_excecoes"])
    assert "contract_id não encontrado em stg_contratos" in excecoes.loc[0, "validation_errors"]
    assert "vigência inicial posterior à final" in excecoes.loc[0, "validation_errors"]
    assert "amendment_value deve ser positivo" in excecoes.loc[0, "validation_errors"]


def test_staging_aditamentos_marca_evento_duplicado_e_aporte_fora_da_renovacao(tmp_path):
    origem = tmp_path / "aditamentos_20260730_120000.csv"
    aditamentos = criar_aditamentos()
    aditamentos.loc[1, "Sequencia_Aditamento"] = 1
    aditamentos.loc[1, "Vigência_Inicio"] = "2027-01-01"
    aditamentos.loc[1, "Vigência_Fim"] = "2027-12-31"
    aditamentos.to_csv(origem, index=False, encoding="utf-8-sig")
    staging = load_staging_module("stg_aditamentos.py")

    erros = staging.validar_aditamentos(staging.preparar_dataframe(origem), {"CS00000001"})

    assert erros.str.contains("evento de aditamento duplicado").all()
    assert "aporte fora da vigência de uma renovação" in erros.iloc[1]


def test_staging_aditamentos_grava_valor_decimal(tmp_path):
    origem = tmp_path / "aditamentos_20260730_120000.csv"
    criar_aditamentos().to_csv(origem, index=False, encoding="utf-8-sig")
    staging = load_staging_module("stg_aditamentos.py")

    resultado = staging.executar_staging(
        origem,
        "20260730_120000",
        date(2026, 7, 30),
        tmp_path / "staging",
        tmp_path / "staging" / "exceptions",
        criar_stg_contratos(tmp_path),
    )

    assert resultado["registros_validos"] == 2
    assert str(pq.read_schema(resultado["arquivo_staging"]).field("amendment_value").type) == "decimal128(18, 2)"
