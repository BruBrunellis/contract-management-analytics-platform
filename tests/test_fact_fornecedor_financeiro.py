from datetime import date

import pandas as pd
from conftest import load_curated_module

LOTE = "20260730_120000"


def criar_fontes(tmp_path):
    staging = tmp_path / "staging"
    curated = tmp_path / "curated"
    staging.mkdir()
    curated.mkdir()
    linhagem = {
        "source_file": "empresas_20260730_120000.csv",
        "source_row_number": 2,
        "load_date": date(2026, 7, 30),
        "batch_id": LOTE,
    }
    empresa = {"cnpj": "11222333000199", **linhagem}
    for ano in range(2022, 2027):
        empresa.update(
            {
                f"faturamento_{ano}": 1_000.0,
                f"custo_{ano}": 700.0,
                f"custo_folha_{ano}": 200.0,
                f"lucro_bruto_{ano}": 300.0,
                f"juros_divida_{ano}": 50.0,
                f"lucro_liquido_{ano}": 200.0,
            }
        )
    pd.DataFrame([empresa]).to_parquet(staging / f"stg_empresas_{LOTE}.parquet", index=False)
    pd.DataFrame(
        {
            "supplier_cnpj": ["11222333000199"],
            "supplier_key": ["SUP-11222333000199"],
            "economic_group_key": ["GRP-11222333"],
        }
    ).to_parquet(curated / f"dim_supplier_{LOTE}.parquet", index=False)
    datas = [date(ano, 12, 31) for ano in range(2022, 2027)]
    pd.DataFrame(
        {
            "calendar_date": datas,
            "calendar_key": [int(data.strftime("%Y%m%d")) for data in datas],
        }
    ).to_parquet(curated / f"dim_calendar_{LOTE}.parquet", index=False)
    return staging, curated


def test_publica_indicadores_financeiros_anuais_por_fornecedor(tmp_path):
    staging, curated_dir = criar_fontes(tmp_path)
    financeiro = load_curated_module("fact_fornecedor_financeiro.py")

    resultado = financeiro.executar_publicacao(LOTE, staging, curated_dir, curated_dir / "exceptions")
    fato = pd.read_parquet(resultado["arquivo_fact_supplier_financial"])

    assert resultado["indicadores_publicados"] == 5
    assert resultado["indicadores_invalidos"] == 0
    assert fato["financial_snapshot_key"].tolist() == [
        f"FIN-11222333000199-{ano}" for ano in range(2022, 2027)
    ]
    assert fato["financial_period_calendar_key"].tolist() == [
        int(f"{ano}1231") for ano in range(2022, 2027)
    ]
    assert fato["gross_revenue"].sum() == 5_000.0
    assert resultado["manifesto"]["financial_coverage"]["is_reconciled"]


def test_isola_indicador_financeiro_sem_fornecedor_resolvido(tmp_path):
    staging, curated_dir = criar_fontes(tmp_path)
    fornecedores = pd.read_parquet(curated_dir / f"dim_supplier_{LOTE}.parquet")
    fornecedores.iloc[0, fornecedores.columns.get_loc("supplier_cnpj")] = "99888777000155"
    fornecedores.to_parquet(curated_dir / f"dim_supplier_{LOTE}.parquet", index=False)
    financeiro = load_curated_module("fact_fornecedor_financeiro.py")

    resultado = financeiro.executar_publicacao(LOTE, staging, curated_dir, curated_dir / "exceptions")
    excecoes = pd.read_parquet(resultado["arquivo_excecoes"])

    assert resultado["indicadores_publicados"] == 0
    assert resultado["indicadores_invalidos"] == 5
    assert excecoes["curated_validation_errors"].str.contains("cnpj não encontrado").all()
