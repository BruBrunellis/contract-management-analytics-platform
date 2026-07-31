import random

from conftest import load_module, load_staging_module


def test_staging_padroniza_identificadores_e_separa_excecoes(tmp_path):
    random.seed(42)
    empresas = load_module("company_generator.py").gerar_tabela_empresas(qtd=20)
    origem = tmp_path / "empresas_20260730_120000.csv"
    empresas.to_csv(origem, index=False, encoding="utf-8-sig")
    staging = load_staging_module()
    preparado = staging.preparar_dataframe(origem)
    erros = staging.validar_empresas(preparado)

    assert erros.eq("").all()
    assert preparado["cnpj"].str.fullmatch(r"\d{14}").all()
    assert preparado["cnpj8"].eq(preparado["cnpj"].str[:8]).all()
    assert {"source_file", "load_date", "source_row_number"}.issubset(preparado.columns)

    invalido = preparado.copy()
    invalido.loc[invalido.index[1], "cnpj"] = invalido.loc[invalido.index[0], "cnpj"]
    assert staging.validar_empresas(invalido).ne("").any()
