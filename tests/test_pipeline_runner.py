from datetime import date
from pathlib import Path

from conftest import load_pipeline_runner


def test_pipeline_runner_gera_arquivos_do_mesmo_lote(tmp_path):
    runner = load_pipeline_runner()
    config = runner.PipelineConfig(qtd_empresas=30, seed=42, data_referencia=date(2026, 7, 30))
    raw_dir = tmp_path / "raw"
    staging_dir = tmp_path / "staging"
    curated_dir = tmp_path / "curated"
    resultado = runner.executar_pipeline(
        config,
        raw_dir=raw_dir,
        staging_dir=staging_dir,
        exceptions_dir=staging_dir / "exceptions",
        curated_dir=curated_dir,
        curated_exceptions_dir=curated_dir / "exceptions",
        identificador_lote="20260730_120000",
    )

    assert Path(resultado["arquivo_manifesto_raw"]).exists()
    assert Path(resultado["arquivo_manifesto_etl"]).exists()
    assert resultado["raw"]["snapshot_id"] == "20260730_120000"
    assert resultado["etl"]["source_snapshot_id"] == "20260730_120000"
    assert resultado["etl"]["staging"]["empresas"]["contract_version"] == "1.0"
    assert resultado["etl"]["curated"]["quality"]["quality_passed"]
