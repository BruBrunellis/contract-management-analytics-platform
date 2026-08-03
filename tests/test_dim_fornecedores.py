from datetime import date

import pandas as pd
from conftest import load_curated_module


def criar_stg_empresas(tmp_path):
    arquivo = tmp_path / "stg_empresas_20260730_120000.parquet"
    empresas = pd.DataFrame(
        [
            {
                "cnpj": "11222333000199",
                "cnpj8": "11222333",
                "cnpj_matriz": "11222333000199",
                "razao_social": "Fornecedor Matriz Ltda.",
                "hierarquia": "Matriz",
                "porte_empresa": "Grande",
                "atividade_economica": "Tecnologia",
                "ano_fundacao": 2000,
                "idade_empresa": 26,
                "estagio_empresa": "Madura",
                "cenario_financeiro": "Normal",
            },
            {
                "cnpj": "11222333000299",
                "cnpj8": "11222333",
                "cnpj_matriz": "11222333000199",
                "razao_social": "Fornecedor Matriz Ltda. - Filial 0002",
                "hierarquia": "Filial",
                "porte_empresa": "Médio",
                "atividade_economica": "Tecnologia",
                "ano_fundacao": 2000,
                "idade_empresa": 26,
                "estagio_empresa": "Madura",
                "cenario_financeiro": "Normal",
            },
            {
                "cnpj": "99888777000155",
                "cnpj8": "99888777",
                "cnpj_matriz": "99888777000155",
                "razao_social": "Outro Fornecedor S.A.",
                "hierarquia": "Matriz",
                "porte_empresa": "Pequeno",
                "atividade_economica": "Consultoria",
                "ano_fundacao": 2015,
                "idade_empresa": 11,
                "estagio_empresa": "Em crescimento",
                "cenario_financeiro": "Expansão",
            },
        ]
    )
    empresas["source_file"] = "empresas_20260730_120000.csv"
    empresas["source_row_number"] = [2, 3, 4]
    empresas["load_date"] = date(2026, 7, 30)
    empresas["batch_id"] = "20260730_120000"
    empresas.to_parquet(arquivo, index=False)
    return arquivo


def test_publica_fornecedores_grupos_e_relacao_matriz_filial(tmp_path):
    staging = criar_stg_empresas(tmp_path)
    curated = load_curated_module()

    resultado = curated.executar_publicacao(
        staging,
        "20260730_120000",
        tmp_path / "curated",
        tmp_path / "curated" / "exceptions",
    )
    fornecedores = pd.read_parquet(resultado["arquivo_dim_supplier"])
    grupos = pd.read_parquet(resultado["arquivo_dim_economic_group"])
    filial = fornecedores.loc[fornecedores["supplier_hierarchy"].eq("Filial")].iloc[0]

    assert resultado["fornecedores_publicados"] == 3
    assert resultado["grupos_publicados"] == 2
    assert fornecedores["supplier_cnpj"].is_unique
    assert grupos["economic_group_cnpj8"].is_unique
    assert filial["parent_supplier_key"] == "SUP-11222333000199"
    assert filial["economic_group_key"] == "GRP-11222333"


def test_publica_excecao_quando_filial_nao_resolve_matriz(tmp_path):
    staging = criar_stg_empresas(tmp_path)
    empresas = pd.read_parquet(staging)
    empresas = empresas.loc[empresas["hierarquia"].eq("Filial")].copy()
    empresas.to_parquet(staging, index=False)
    curated = load_curated_module()

    resultado = curated.executar_publicacao(
        staging,
        "20260730_120000",
        tmp_path / "curated",
        tmp_path / "curated" / "exceptions",
    )
    excecoes = pd.read_parquet(resultado["arquivo_excecoes"])

    assert resultado["fornecedores_publicados"] == 0
    assert resultado["registros_invalidos"] == 1
    assert "cnpj_matriz não encontrado como matriz" in excecoes.loc[0, "curated_validation_errors"]
    assert "grupo econômico sem matriz única" in excecoes.loc[0, "curated_validation_errors"]


def test_publica_excecao_quando_grupo_tem_mais_de_uma_matriz(tmp_path):
    staging = criar_stg_empresas(tmp_path)
    empresas = pd.read_parquet(staging)
    matriz_duplicada = empresas.iloc[0].copy()
    matriz_duplicada["cnpj"] = "11222333000399"
    matriz_duplicada["cnpj_matriz"] = "11222333000399"
    matriz_duplicada["source_row_number"] = 5
    empresas.loc[len(empresas)] = matriz_duplicada
    empresas.to_parquet(staging, index=False)
    curated = load_curated_module()

    resultado = curated.executar_publicacao(
        staging,
        "20260730_120000",
        tmp_path / "curated",
        tmp_path / "curated" / "exceptions",
    )
    excecoes = pd.read_parquet(resultado["arquivo_excecoes"])

    assert resultado["fornecedores_publicados"] == 1
    assert resultado["grupos_publicados"] == 1
    assert excecoes["curated_validation_errors"].str.contains("grupo econômico sem matriz única").all()
