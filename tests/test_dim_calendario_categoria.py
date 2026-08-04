from datetime import date

import pandas as pd
from conftest import load_curated_module

LOTE = "20260730_120000"


def criar_stagings(tmp_path):
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    pd.DataFrame(
        {
            "validity_start_date": [date(2026, 1, 10)],
            "validity_end_date": [date(2026, 12, 31)],
            "risk_evaluation_date": [date(2026, 1, 9)],
            "load_date": [date(2026, 7, 30)],
            "contract_category": ["licenca_de_software"],
        }
    ).to_parquet(staging_dir / f"stg_contratos_{LOTE}.parquet", index=False)
    pd.DataFrame(
        {
            "validity_start_date": [date(2026, 2, 1)],
            "validity_end_date": [date(2027, 1, 2)],
            "load_date": [date(2026, 7, 30)],
        }
    ).to_parquet(staging_dir / f"stg_aditamentos_{LOTE}.parquet", index=False)
    pd.DataFrame(
        {
            "payment_date": [date(2026, 3, 15)],
            "load_date": [date(2026, 7, 30)],
            "payment_category": ["consultoria"],
        }
    ).to_parquet(staging_dir / f"stg_pagamentos_{LOTE}.parquet", index=False)
    pd.DataFrame(
        {
            "assessment_date": [date(2025, 12, 31)],
            "last_approval_date": [date(2026, 1, 1)],
            "expiration_date": [date(2026, 12, 30)],
            "load_date": [date(2026, 7, 30)],
        }
    ).to_parquet(staging_dir / f"stg_homologacoes_risco_{LOTE}.parquet", index=False)
    return staging_dir


def test_dim_calendar_cobre_datas_e_tem_chaves_unicas(tmp_path):
    curated = load_curated_module("dim_calendario_categoria.py")
    resultado = curated.executar_publicacao(LOTE, criar_stagings(tmp_path), tmp_path / "curated")
    calendario = pd.read_parquet(resultado["arquivo_dim_calendar"])

    assert calendario["calendar_key"].is_unique
    assert calendario["calendar_date"].is_unique
    assert calendario["calendar_date"].min() == date(2025, 12, 31)
    assert calendario["calendar_date"].max() == date(2027, 1, 2)
    assert len(calendario) == 368
    assert calendario.loc[calendario["calendar_date"].eq(date(2026, 1, 10)), "is_weekend"].item()
    assert calendario.loc[calendario["calendar_date"].eq(date(2026, 12, 31)), "is_year_end"].item()


def test_dim_category_unifica_codigos_e_aplica_tres_niveis(tmp_path):
    curated = load_curated_module("dim_calendario_categoria.py")
    fontes = curated.carregar_fontes(LOTE, criar_stagings(tmp_path))
    fontes["stg_pagamentos"].loc[1] = [date(2026, 3, 16), date(2026, 7, 30), "categoria_nova"]

    categorias = curated.construir_dim_category(fontes)
    software = categorias.loc[categorias["category_code"].eq("licenca_de_software")].iloc[0]
    desconhecida = categorias.loc[categorias["category_code"].eq("categoria_nova")].iloc[0]

    assert categorias["category_key"].is_unique
    assert categorias["category_code"].is_unique
    assert software["category_key"] == "CAT-licenca_de_software"
    assert software["category_macro_group"] == "opex_focused"
    assert software["category_group"] == "tecnologia"
    assert software["category_family"] == "software_e_licencas"
    assert not desconhecida["is_taxonomy_mapped"]
    assert {desconhecida["category_macro_group"], desconhecida["category_group"], desconhecida["category_family"]} == {"nao_classificada"}
