from datetime import date

import pandas as pd
import pyarrow.parquet as pq
from conftest import load_staging_module


def criar_pagamentos():
    return pd.DataFrame(
        [
            {
                "Cód_Pagamento": "PAG00000001",
                "Cód_Contrato": "CS00000001",
                "CNPJ": "13.241.241/0001-55",
                "Fornecedor": "Fornecedor Exemplo S.A.",
                "Data_Pagamento": "2026-07-15",
                "Valor_Pago": 450.00,
                "Centro_Custo": "CC-300",
                "Categoria": "Licença de Software",
            }
        ]
    )


def criar_stg_contratos(tmp_path):
    arquivo = tmp_path / "stg_contratos_20260730_120000.parquet"
    pd.DataFrame({"contract_id": ["CS00000001"]}).to_parquet(arquivo, index=False)
    return arquivo


def test_staging_pagamentos_padroniza_e_valida_referencia(tmp_path):
    origem = tmp_path / "spending_ficticio_20260730_120000.csv"
    criar_pagamentos().to_csv(origem, index=False, encoding="utf-8-sig")
    staging = load_staging_module("stg_pagamentos.py")

    preparado = staging.preparar_dataframe(origem, date(2026, 7, 30))
    erros = staging.validar_pagamentos(preparado, {"CS00000001"})

    assert erros.eq("").all()
    assert preparado.loc[0, "supplier_cnpj8"] == "13241241"
    assert preparado.loc[0, "payment_category"] == "licenca_de_software"
    assert preparado.loc[0, "batch_id"] == "20260730_120000"


def test_staging_pagamentos_separa_excecoes_e_grava_decimal(tmp_path):
    origem = tmp_path / "spending_ficticio_20260730_120000.csv"
    pagamentos = criar_pagamentos()
    pagamentos.loc[1] = pagamentos.loc[0]
    pagamentos.loc[1, "Cód_Pagamento"] = "PAG00000002"
    pagamentos.loc[1, "Cód_Contrato"] = "CS99999999"
    pagamentos.loc[1, "Data_Pagamento"] = "data-inválida"
    pagamentos.loc[1, "Valor_Pago"] = 0
    pagamentos.to_csv(origem, index=False, encoding="utf-8-sig")
    staging = load_staging_module("stg_pagamentos.py")

    resultado = staging.executar_staging(
        origem,
        "20260730_120000",
        date(2026, 7, 30),
        tmp_path / "staging",
        tmp_path / "staging" / "exceptions",
        criar_stg_contratos(tmp_path),
    )

    assert resultado["registros_validos"] == 1
    assert resultado["registros_invalidos"] == 1
    assert str(pq.read_schema(resultado["arquivo_staging"]).field("payment_value").type) == "decimal128(18, 2)"
    excecoes = pd.read_parquet(resultado["arquivo_excecoes"])
    assert "contract_id não encontrado em stg_contratos" in excecoes.loc[0, "validation_errors"]
    assert "payment_date ausente ou inválida" in excecoes.loc[0, "validation_errors"]
    assert "payment_value deve ser positivo" in excecoes.loc[0, "validation_errors"]


def test_staging_pagamentos_marca_payment_id_duplicado(tmp_path):
    origem = tmp_path / "spending_ficticio_20260730_120000.csv"
    pagamentos = criar_pagamentos()
    pagamentos.loc[1] = pagamentos.loc[0]
    pagamentos.to_csv(origem, index=False, encoding="utf-8-sig")
    staging = load_staging_module("stg_pagamentos.py")

    erros = staging.validar_pagamentos(staging.preparar_dataframe(origem), {"CS00000001"})

    assert erros.str.contains("payment_id duplicado").all()
