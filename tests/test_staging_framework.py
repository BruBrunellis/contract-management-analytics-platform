from datetime import date

import pandas as pd
import pytest
from conftest import load_staging_module


def test_framework_adiciona_linhagem_e_conta_erros(tmp_path):
    framework = load_staging_module("staging_framework.py")
    origem = tmp_path / "fonte_20260730_120000.csv"
    dataframe = framework.adicionar_linhagem(pd.DataFrame({"chave": ["a", "b"]}), origem, date(2026, 7, 30))
    erros = pd.Series(["chave inválida; data inválida", "chave inválida"], dtype="string")

    assert dataframe["source_row_number"].tolist() == [2, 3]
    assert dataframe["batch_id"].tolist() == ["20260730_120000", "20260730_120000"]
    assert framework.contar_erros(erros) == {"chave inválida": 2, "data inválida": 1}


def test_framework_rejeita_coluna_obrigatoria_ausente():
    framework = load_staging_module("staging_framework.py")

    with pytest.raises(framework.SchemaContractError, match="colunas obrigatórias"):
        framework.validar_colunas_obrigatorias(["id"], ["id", "valor"], "teste")
