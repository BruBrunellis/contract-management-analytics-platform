from datetime import date
from decimal import Decimal

import pandas as pd
from conftest import load_curated_module

LOTE = "20260730_120000"


def escrever(df, diretorio, tabela):
    df.to_parquet(diretorio / f"{tabela}_{LOTE}.parquet", index=False)


def criar_artefatos(tmp_path):
    staging = tmp_path / "staging"
    curated = tmp_path / "curated"
    exceptions = curated / "exceptions"
    staging.mkdir()
    curated.mkdir()
    exceptions.mkdir()
    linhagem = {
        "source_file": "fonte_20260730_120000.csv",
        "source_row_number": 2,
        "load_date": date(2026, 7, 30),
        "batch_id": LOTE,
    }
    escrever(pd.DataFrame({"cnpj": ["11222333000199"]}), staging, "stg_empresas")
    escrever(
        pd.DataFrame(
            {
                "contract_id": ["CS00000001"],
                "contract_category": ["consultoria"],
                "validity_start_date": [date(2026, 1, 1)],
                "validity_end_date": [date(2026, 12, 31)],
                "risk_evaluation_date": [None],
            }
        ),
        staging,
        "stg_contratos",
    )
    escrever(
        pd.DataFrame(
            {
                "payment_id": ["PAG00000001"],
                "payment_date": [date(2026, 2, 1)],
                "payment_category": ["consultoria"],
                "payment_value": [Decimal("100.00")],
            }
        ),
        staging,
        "stg_pagamentos",
    )
    escrever(
        pd.DataFrame(
            {
                "risk_assessment_id": ["RSK000000001"],
                "assessment_date": [date(2026, 1, 1)],
                "last_approval_date": [None],
                "expiration_date": [None],
            }
        ),
        staging,
        "stg_homologacoes_risco",
    )
    escrever(
        pd.DataFrame(
            {
                "amendment_id": ["AMD-CS00000001-0001"],
                "validity_start_date": [date(2026, 2, 1)],
                "validity_end_date": [date(2026, 12, 31)],
                "amendment_value": [Decimal("20.00")],
            }
        ),
        staging,
        "stg_aditamentos",
    )
    escrever(
        pd.DataFrame(
            {"supplier_cnpj": ["11222333000199"], "economic_group_key": ["GRP-11222333"]}
        ),
        curated,
        "dim_supplier",
    )
    escrever(pd.DataFrame({"economic_group_key": ["GRP-11222333"]}), curated, "dim_economic_group")
    calendario = pd.date_range(date(2026, 1, 1), date(2026, 12, 31), freq="D")
    escrever(
        pd.DataFrame(
            {
                "calendar_date": calendario.date,
                "calendar_key": calendario.strftime("%Y%m%d").astype("int64"),
            }
        ),
        curated,
        "dim_calendar",
    )
    escrever(pd.DataFrame({"category_code": ["consultoria"], "category_key": ["CAT-consultoria"]}), curated, "dim_category")
    escrever(pd.DataFrame({"contract_id": ["CS00000001"]}), curated, "dim_contract")
    escrever(
        pd.DataFrame({"payment_id": ["PAG00000001"], "payment_value": [Decimal("100.00")]}),
        curated,
        "fact_spending",
    )
    escrever(pd.DataFrame({"risk_assessment_id": ["RSK000000001"]}), curated, "fact_rfi")
    escrever(
        pd.DataFrame({"amendment_id": ["AMD-CS00000001-0001"], "amendment_value": [Decimal("20.00")]}),
        curated,
        "fact_renewal",
    )
    for tabela, chave, valor in [
        ("dim_supplier_resolution_exceptions", "cnpj", None),
        ("dim_contract_resolution_exceptions", "contract_id", None),
        ("fact_spending_exceptions", "payment_id", "payment_value"),
        ("fact_rfi_exceptions", "risk_assessment_id", None),
        ("fact_renewal_exceptions", "amendment_id", "amendment_value"),
    ]:
        colunas = {chave: pd.Series(dtype="string"), "curated_validation_errors": pd.Series(dtype="string")}
        if valor:
            colunas[valor] = pd.Series(dtype=object)
        for coluna in linhagem:
            colunas[coluna] = pd.Series(dtype=object)
        escrever(pd.DataFrame(colunas), exceptions, tabela)
    return staging, curated, exceptions, linhagem


def test_reconciliacao_aprovada_publica_relatorio(tmp_path):
    staging, curated_dir, exceptions, _ = criar_artefatos(tmp_path)
    quality = load_curated_module("reconciliacoes_curated.py")

    resultado = quality.executar_reconciliacoes(LOTE, staging, curated_dir, exceptions)
    relatorio = pd.read_parquet(resultado["arquivo_relatorio"])

    assert resultado["quality_passed"]
    assert len(relatorio) == 8
    assert relatorio["status"].eq("approved").all()
    assert relatorio.loc[relatorio["entity"].eq("fact_spending"), "source_monetary_total"].item() == "100.00"


def test_match_rate_reprovado_consolida_indice_de_excecoes(tmp_path):
    staging, curated_dir, exceptions, linhagem = criar_artefatos(tmp_path)
    escrever(pd.DataFrame({"payment_id": pd.Series(dtype="string"), "payment_value": pd.Series(dtype=object)}), curated_dir, "fact_spending")
    escrever(
        pd.DataFrame(
            [
                {
                    "payment_id": "PAG00000001",
                    "payment_value": Decimal("100.00"),
                    "curated_validation_errors": "contract_id não encontrado em dim_contract",
                    **linhagem,
                }
            ]
        ),
        exceptions,
        "fact_spending_exceptions",
    )
    quality = load_curated_module("reconciliacoes_curated.py")

    resultado = quality.executar_reconciliacoes(LOTE, staging, curated_dir, exceptions, min_match_rate=0.95)
    indice = pd.read_parquet(resultado["arquivo_indice_excecoes"])

    assert not resultado["quality_passed"]
    assert "fact_spending" in resultado["entidades_reprovadas"]
    assert indice.loc[0, "business_key"] == "PAG00000001"
    assert "contract_id não encontrado" in indice.loc[0, "exception_cause"]
