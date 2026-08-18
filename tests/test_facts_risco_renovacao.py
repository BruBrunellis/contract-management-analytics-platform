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
                "risk_assessment_id": "RSK000000001",
                "supplier_cnpj": "11222333000199",
                "assessment_date": date(2026, 1, 10),
                "last_approval_date": date(2026, 1, 1),
                "expiration_date": date(2026, 12, 31),
                "homologation_result": "aprovada",
                "homologation_status": "ativa",
                "financial_risk": "baixo",
                "labor_risk": "baixo",
                "credit_rating": "AA",
                "final_risk": "baixo",
                "interest_to_revenue_ratio": 0.1,
                "revenue_trend": 0.2,
                "net_margin": 0.3,
                "labor_cases_index": 0.01,
                **linhagem,
            }
        ]
    ).to_parquet(staging_dir / f"stg_homologacoes_risco_{LOTE}.parquet", index=False)
    pd.DataFrame(
        [
            {
                "amendment_id": "AMD-CS00000001-0001",
                "contract_id": "CS00000001",
                "amendment_type": "renovacao",
                "validity_start_date": date(2026, 2, 1),
                "validity_end_date": date(2026, 12, 31),
                "amendment_value": Decimal("500.00"),
                "amendment_sequence": 1,
                **linhagem,
            },
            {
                "amendment_id": "AMD-CS00000001-0002",
                "contract_id": "CS00000001",
                "amendment_type": "aporte",
                "validity_start_date": date(2026, 6, 1),
                "validity_end_date": date(2026, 12, 31),
                "amendment_value": Decimal("100.00"),
                "amendment_sequence": 2,
                **linhagem,
            },
        ]
    ).to_parquet(staging_dir / f"stg_aditamentos_{LOTE}.parquet", index=False)
    pd.DataFrame(
        {
            "supplier_cnpj": ["11222333000199"],
            "supplier_key": ["SUP-11222333000199"],
            "economic_group_key": ["GRP-11222333"],
        }
    ).to_parquet(curated_dir / f"dim_supplier_{LOTE}.parquet", index=False)
    pd.DataFrame(
        {
            "contract_id": ["CS00000001"],
            "contract_key": ["CON-CS00000001"],
            "supplier_key": ["SUP-11222333000199"],
            "economic_group_key": ["GRP-11222333"],
            "category_key": ["CAT-consultoria"],
        }
    ).to_parquet(curated_dir / f"dim_contract_{LOTE}.parquet", index=False)
    pd.DataFrame(
        {
            "calendar_date": [
                date(2026, 1, 1),
                date(2026, 1, 10),
                date(2026, 2, 1),
                date(2026, 6, 1),
                date(2026, 12, 31),
            ],
            "calendar_key": [20260101, 20260110, 20260201, 20260601, 20261231],
        }
    ).to_parquet(curated_dir / f"dim_calendar_{LOTE}.parquet", index=False)
    return staging_dir, curated_dir


def test_publica_fatos_rfi_e_renewal_com_integridade(tmp_path):
    staging_dir, curated_dir = criar_fontes(tmp_path)
    curated = load_curated_module("facts_risco_renovacao.py")

    resultado = curated.executar_publicacao(LOTE, staging_dir, curated_dir, curated_dir / "exceptions")
    rfi = pd.read_parquet(resultado["arquivo_fact_rfi"])
    renovacoes = pd.read_parquet(resultado["arquivo_fact_renewal"])

    assert resultado["rfi_publicados"] == 1
    assert resultado["renovacoes_publicadas"] == 2
    assert rfi.loc[0, "rfi_key"] == "RFI-RSK000000001"
    assert rfi.loc[0, "assessment_calendar_key"] == 20260110
    assert renovacoes.loc[0, "renewal_key"] == "RNL-AMD-CS00000001-0001"
    assert renovacoes.loc[0, "is_renewal"]
    assert not renovacoes.loc[1, "is_renewal"]
    assert resultado["manifesto"]["renewal_coverage"]["is_reconciled"]


def test_eventos_sem_fornecedor_ou_contrato_vao_para_excecao(tmp_path):
    staging_dir, curated_dir = criar_fontes(tmp_path)
    riscos = pd.read_parquet(staging_dir / f"stg_homologacoes_risco_{LOTE}.parquet")
    riscos.loc[0, "supplier_cnpj"] = "99888777000155"
    riscos.to_parquet(staging_dir / f"stg_homologacoes_risco_{LOTE}.parquet", index=False)
    aditamentos = pd.read_parquet(staging_dir / f"stg_aditamentos_{LOTE}.parquet")
    aditamentos.loc[1, "contract_id"] = "CS99999999"
    aditamentos.to_parquet(staging_dir / f"stg_aditamentos_{LOTE}.parquet", index=False)
    curated = load_curated_module("facts_risco_renovacao.py")

    resultado = curated.executar_publicacao(LOTE, staging_dir, curated_dir, curated_dir / "exceptions")
    excecoes_rfi = pd.read_parquet(resultado["arquivo_excecoes_rfi"])
    excecoes_renovacao = pd.read_parquet(resultado["arquivo_excecoes_renovacao"])

    assert resultado["rfi_invalidos"] == 1
    assert resultado["renovacoes_invalidas"] == 1
    assert "supplier_cnpj não encontrado em dim_supplier" in excecoes_rfi.loc[0, "curated_validation_errors"]
    assert "contract_id não encontrado em dim_contract" in excecoes_renovacao.loc[0, "curated_validation_errors"]
