import json
from datetime import date
from pathlib import Path

from conftest import load_pipeline_runner


def test_pipeline_runner_gera_arquivos_do_mesmo_lote(tmp_path):
    runner = load_pipeline_runner()
    config = runner.PipelineConfig(qtd_empresas=30, seed=42, data_referencia=date(2026, 7, 30))
    raw_dir = tmp_path / "raw"
    staging_dir = tmp_path / "staging"
    resultado = runner.executar_pipeline(
        config,
        raw_dir=raw_dir,
        staging_dir=staging_dir,
        exceptions_dir=staging_dir / "exceptions",
        identificador_lote="20260730_120000",
    )

    for arquivo in resultado["arquivos"].values():
        assert Path(arquivo).exists()
    manifesto = json.loads(Path(resultado["arquivos"]["manifesto"]).read_text(encoding="utf-8"))
    assert manifesto["identificador_lote"] == "20260730_120000"
    assert manifesto["contagens"]["empresas"] >= 30
    assert manifesto["staging"]["contratos"]["row_counts"]["valid"] == manifesto["contagens"]["stg_contratos_validos"]
    assert manifesto["staging"]["empresas"]["contract_version"] == "1.0"
    assert manifesto["staging"]["pagamentos"]["row_counts"]["valid"] == manifesto["contagens"]["stg_pagamentos_validos"]
    assert manifesto["staging"]["homologacoes_risco"]["row_counts"]["valid"] == manifesto["contagens"]["stg_homologacoes_risco_validas"]
