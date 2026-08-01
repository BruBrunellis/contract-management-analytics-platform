from datetime import date

import pandas as pd
import pyarrow.parquet as pq
from conftest import load_staging_module


def criar_contratos():
    return pd.DataFrame(
        [
            {
                "Cód_Contrato": "CS00000001",
                "Nome_Contrato": "Contrato de Serviços",
                "CNPJ": "13.241.241/0001-55",
                "Fornecedor": "Fornecedor Exemplo S.A.",
                "Escopo": "Serviços de Infraestrutura",
                "Vigência Inicio": "2026-01-01",
                "Vigência Fim": "2026-12-31",
                "Valor_Original": 1000.00,
                "Valor_Total": 1200.00,
                "Saldo": 300.00,
                "Tipo_Contrato": "Contrato Renovado",
                "Status": "Ativo",
                "Data_Avaliacao_Risco": "",
                "Risco_Final": "Médio",
                "Motivo_Encerramento": "",
            }
        ]
    )


def test_staging_contratos_padroniza_schema_e_linhagem(tmp_path):
    origem = tmp_path / "contratos_ficticios_20260730_120000.csv"
    criar_contratos().to_csv(origem, index=False, encoding="utf-8-sig")
    staging = load_staging_module("stg_contratos.py")

    preparado = staging.preparar_dataframe(origem, date(2026, 7, 30))
    erros = staging.validar_contratos(preparado)

    assert erros.eq("").all()
    assert preparado.loc[0, "supplier_cnpj"] == "13241241000155"
    assert preparado.loc[0, "contract_status"] == "ativo"
    assert preparado.loc[0, "contract_category"] == "servicos_de_infraestrutura"
    assert preparado.loc[0, "batch_id"] == "20260730_120000"
    assert {"source_file", "source_row_number", "load_date", "batch_id"}.issubset(preparado.columns)


def test_staging_contratos_isola_erros_e_grava_decimal_no_parquet(tmp_path):
    origem = tmp_path / "contratos_ficticios_20260730_120000.csv"
    contratos = criar_contratos()
    contratos.loc[1] = contratos.loc[0]
    contratos.loc[1, "Cód_Contrato"] = "CS00000002"
    contratos.loc[1, "Vigência Inicio"] = "2027-01-01"
    contratos.loc[1, "Vigência Fim"] = "2026-12-31"
    contratos.loc[1, "Valor_Total"] = -1
    contratos.to_csv(origem, index=False, encoding="utf-8-sig")
    staging = load_staging_module("stg_contratos.py")

    resultado = staging.executar_staging(
        origem,
        "20260730_120000",
        date(2026, 7, 30),
        tmp_path / "staging",
        tmp_path / "staging" / "exceptions",
    )

    assert resultado["registros_validos"] == 1
    assert resultado["registros_invalidos"] == 1
    assert str(pq.read_schema(resultado["arquivo_staging"]).field("original_value").type) == "decimal128(18, 2)"
    excecoes = pd.read_parquet(resultado["arquivo_excecoes"])
    assert "vigência inicial posterior à final" in excecoes.loc[0, "validation_errors"]


def test_staging_contratos_valida_campos_de_encerramento(tmp_path):
    origem = tmp_path / "contratos_ficticios_20260730_120000.csv"
    contratos = criar_contratos()
    contratos.loc[0, "Status"] = "Encerrado"
    contratos.to_csv(origem, index=False, encoding="utf-8-sig")
    staging = load_staging_module("stg_contratos.py")

    erros = staging.validar_contratos(staging.preparar_dataframe(origem))

    assert "encerrado sem data de avaliação de risco" in erros.loc[0]
    assert "encerrado sem motivo de encerramento" in erros.loc[0]


def test_staging_contratos_marca_contract_id_duplicado(tmp_path):
    origem = tmp_path / "contratos_ficticios_20260730_120000.csv"
    contratos = criar_contratos()
    contratos.loc[1] = contratos.loc[0]
    contratos.to_csv(origem, index=False, encoding="utf-8-sig")
    staging = load_staging_module("stg_contratos.py")

    erros = staging.validar_contratos(staging.preparar_dataframe(origem))

    assert erros.str.contains("contract_id duplicado").all()
