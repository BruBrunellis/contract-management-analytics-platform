from datetime import date
from decimal import Decimal

import pandas as pd
from conftest import load_curated_module

LOTE = "20260730_120000"


def criar_fontes(tmp_path):
    staging_dir = tmp_path / "staging"
    curated_dir = tmp_path / "curated"
    staging_dir.mkdir()
    curated_dir.mkdir()
    linhagem = {
        "source_file": "fonte_20260730_120000.csv",
        "source_row_number": 2,
        "load_date": date(2026, 7, 30),
        "batch_id": LOTE,
    }
    pd.DataFrame(
        [
            {
                "contract_id": "CS00000001",
                "contract_name": "Contrato de consultoria",
                "supplier_cnpj": "11222333000199",
                "contract_category": "consultoria",
                "validity_start_date": date(2026, 1, 1),
                "validity_end_date": date(2026, 12, 31),
                "original_value": Decimal("1000.00"),
                "total_value": Decimal("1000.00"),
                "balance_value": Decimal("500.00"),
                "contract_type": "novo_contrato",
                "contract_status": "ativo",
                "risk_evaluation_date": None,
                "final_risk": "baixo",
                "closure_reason": None,
                **linhagem,
            }
        ]
    ).to_parquet(staging_dir / f"stg_contratos_{LOTE}.parquet", index=False)
    pd.DataFrame(
        [
            {
                "payment_id": "PAG00000001",
                "contract_id": "CS00000001",
                "supplier_cnpj": "11222333000199",
                "payment_date": date(2026, 2, 15),
                "payment_value": Decimal("500.00"),
                "cost_center": "CC-100",
                "payment_category": "consultoria",
                **linhagem,
            }
        ]
    ).to_parquet(staging_dir / f"stg_pagamentos_{LOTE}.parquet", index=False)
    pd.DataFrame(
        {
            "supplier_cnpj": ["11222333000199"],
            "supplier_key": ["SUP-11222333000199"],
            "economic_group_key": ["GRP-11222333"],
        }
    ).to_parquet(curated_dir / f"dim_supplier_{LOTE}.parquet", index=False)
    pd.DataFrame(
        {"category_code": ["consultoria"], "category_key": ["CAT-consultoria"]}
    ).to_parquet(curated_dir / f"dim_category_{LOTE}.parquet", index=False)
    pd.DataFrame(
        {
            "calendar_date": [date(2026, 1, 1), date(2026, 2, 15), date(2026, 12, 31)],
            "calendar_key": [20260101, 20260215, 20261231],
        }
    ).to_parquet(curated_dir / f"dim_calendar_{LOTE}.parquet", index=False)
    return staging_dir, curated_dir


def test_publica_dim_contract_e_fact_spending_com_chaves_resolvidas(tmp_path):
    staging_dir, curated_dir = criar_fontes(tmp_path)
    curated = load_curated_module("dim_contratos_gastos.py")

    resultado = curated.executar_publicacao(LOTE, staging_dir, curated_dir, curated_dir / "exceptions")
    contratos = pd.read_parquet(resultado["arquivo_dim_contract"])
    gastos = pd.read_parquet(resultado["arquivo_fact_spending"])

    assert resultado["contratos_publicados"] == 1
    assert resultado["pagamentos_publicados"] == 1
    assert contratos.loc[0, "contract_key"] == "CON-CS00000001"
    assert gastos.loc[0, "spending_key"] == "SPN-PAG00000001"
    assert gastos.loc[0, "supplier_key"] == "SUP-11222333000199"
    assert gastos.loc[0, "payment_calendar_key"] == 20260215
    assert resultado["manifesto"]["spending_reconciliation"]["is_payment_value_reconciled"]


def test_pagamento_sem_contrato_publicado_vai_para_excecao_e_reconcilia(tmp_path):
    staging_dir, curated_dir = criar_fontes(tmp_path)
    pagamentos = pd.read_parquet(staging_dir / f"stg_pagamentos_{LOTE}.parquet")
    pagamentos.loc[1] = pagamentos.loc[0]
    pagamentos.loc[1, "payment_id"] = "PAG00000002"
    pagamentos.loc[1, "contract_id"] = "CS99999999"
    pagamentos.loc[1, "payment_value"] = Decimal("250.00")
    pagamentos.to_parquet(staging_dir / f"stg_pagamentos_{LOTE}.parquet", index=False)
    curated = load_curated_module("dim_contratos_gastos.py")

    resultado = curated.executar_publicacao(LOTE, staging_dir, curated_dir, curated_dir / "exceptions")
    excecoes = pd.read_parquet(resultado["arquivo_excecoes_pagamentos"])
    reconciliacao = resultado["manifesto"]["spending_reconciliation"]

    assert resultado["pagamentos_publicados"] == 1
    assert resultado["pagamentos_invalidos"] == 1
    assert "contract_id não encontrado em dim_contract" in excecoes.loc[0, "curated_validation_errors"]
    assert reconciliacao["is_row_count_reconciled"]
    assert reconciliacao["source_payment_value"] == "750.00"


def test_contrato_sem_fornecedor_dimensionado_vai_para_excecao(tmp_path):
    staging_dir, curated_dir = criar_fontes(tmp_path)
    contratos = pd.read_parquet(staging_dir / f"stg_contratos_{LOTE}.parquet")
    contratos.loc[0, "supplier_cnpj"] = "99888777000155"
    contratos.to_parquet(staging_dir / f"stg_contratos_{LOTE}.parquet", index=False)
    curated = load_curated_module("dim_contratos_gastos.py")

    resultado = curated.executar_publicacao(LOTE, staging_dir, curated_dir, curated_dir / "exceptions")
    excecoes = pd.read_parquet(resultado["arquivo_excecoes_contratos"])

    assert resultado["contratos_publicados"] == 0
    assert "supplier_cnpj não encontrado em dim_supplier" in excecoes.loc[0, "curated_validation_errors"]
