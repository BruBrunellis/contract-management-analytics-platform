import importlib.util
import json
import sys
from datetime import date

import duckdb
import pytest
from conftest import PROJECT_ROOT

SCRIPT_DIR = PROJECT_ROOT / "2.scr"


def carregar_script(caminho_relativo):
    caminho = SCRIPT_DIR / caminho_relativo
    if str(caminho.parent) not in sys.path:
        sys.path.insert(0, str(caminho.parent))
    spec = importlib.util.spec_from_file_location(caminho.stem, caminho)
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[caminho.stem] = modulo
    spec.loader.exec_module(modulo)
    return modulo


def gerar_manifesto_etl(tmp_path):
    generate = carregar_script("generate_raw.py")
    etl = carregar_script("run_etl.py")
    raw = generate.gerar_snapshot_inicial(
        generate.RawGenerationConfig(
            scenario_id="analytics_test",
            qtd_empresas=20,
            seed=42,
            data_referencia=date(2026, 7, 30),
        ),
        tmp_path / "raw",
        snapshot_id="20260730_120000",
    )
    return etl.executar_etl(
        raw["arquivo_manifesto"], data_dir=tmp_path / "data", pipeline_run_id="etl_analytics_test"
    )["arquivo_manifesto"]


def test_recria_views_duckdb_por_manifesto_etl(tmp_path):
    arquivo_manifesto = gerar_manifesto_etl(tmp_path)
    analytics = carregar_script("4.analytics/build_analytics.py")
    arquivo_banco = tmp_path / "analytics.duckdb"

    resultado = analytics.recriar_views(arquivo_manifesto, arquivo_banco)

    assert resultado["database_path"] == arquivo_banco
    with duckdb.connect(str(arquivo_banco), read_only=True) as conexao:
        assert conexao.execute("SELECT COUNT(*) FROM vw_contracts").fetchone()[0] > 0
        assert conexao.execute("SELECT COUNT(*) FROM vw_spending").fetchone()[0] > 0
        assert conexao.execute("SELECT COUNT(*) FROM vw_renewals").fetchone()[0] >= 0
        contexto = conexao.execute(
            "SELECT pipeline_run_id, source_snapshot_id FROM analytics_run_context"
        ).fetchone()
        assert contexto == ("etl_analytics_test", "20260730_120000")
        colunas = conexao.execute("DESCRIBE vw_quality_reconciliation").fetchdf()["column_name"].tolist()
        assert {"pipeline_run_id", "source_snapshot_id", "match_rate", "status"}.issubset(colunas)


def test_rejeita_manifesto_com_quality_gate_reprovado(tmp_path):
    arquivo_manifesto = gerar_manifesto_etl(tmp_path)
    analytics_framework = carregar_script("4.analytics/analytics_framework.py")
    dados = json.loads(arquivo_manifesto.read_text(encoding="utf-8"))
    dados["curated"]["quality"]["quality_passed"] = False
    manifesto_invalido = tmp_path / "etl_manifest_invalid.json"
    manifesto_invalido.write_text(json.dumps(dados), encoding="utf-8")

    with pytest.raises(analytics_framework.AnalyticsContractError, match="quality gate"):
        analytics_framework.carregar_entrada(manifesto_invalido)
