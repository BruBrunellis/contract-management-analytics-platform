import importlib.util
import sys
from datetime import date
from pathlib import Path

import pandas as pd
from conftest import PROJECT_ROOT

SCRIPT_DIR = PROJECT_ROOT / "2.scr"


def carregar_script(nome):
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    caminho = SCRIPT_DIR / nome
    spec = importlib.util.spec_from_file_location(caminho.stem, caminho)
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[caminho.stem] = modulo
    spec.loader.exec_module(modulo)
    return modulo


def test_snapshot_inicial_atualizacao_e_etl_por_manifesto(tmp_path):
    generate = carregar_script("generate_raw.py")
    update = carregar_script("update_raw.py")
    etl = carregar_script("run_etl.py")
    raw_dir = tmp_path / "raw"
    data_dir = tmp_path / "data"
    inicial = generate.gerar_snapshot_inicial(
        generate.RawGenerationConfig(
            scenario_id="cenario_teste",
            qtd_empresas=20,
            seed=42,
            data_referencia=date(2026, 7, 30),
        ),
        raw_dir,
        snapshot_id="20260730_120000",
    )
    manifesto_inicial = inicial["arquivo_manifesto"]
    contratos_pai = pd.read_csv(
        manifesto_inicial.parent / inicial["manifesto"]["sources"]["contratos"]["path"]
    )

    atualizado = update.atualizar_snapshot(
        manifesto_inicial,
        update.RawUpdateConfig(
            data_referencia=date(2026, 9, 30),
            seed=99,
            probabilidade_novos_fornecedores=0.10,
            probabilidade_novos_contratos=1.0,
            probabilidade_novos_pagamentos=1.0,
            probabilidade_reavaliacao_risco=1.0,
        ),
        raw_dir,
        snapshot_id="20260930_120000",
    )
    contratos_pai_apos = pd.read_csv(
        manifesto_inicial.parent / inicial["manifesto"]["sources"]["contratos"]["path"]
    )
    assert contratos_pai.equals(contratos_pai_apos)
    assert atualizado["manifesto"]["parent_snapshot_id"] == "20260730_120000"
    assert atualizado["manifesto"]["sources"]["pagamentos"]["row_count"] >= inicial["manifesto"]["sources"]["pagamentos"]["row_count"]

    resultado_etl = etl.executar_etl(
        atualizado["arquivo_manifesto"], data_dir=data_dir, pipeline_run_id="etl_teste"
    )
    manifesto_etl = resultado_etl["manifesto"]
    assert manifesto_etl["source_snapshot_id"] == "20260930_120000"
    assert manifesto_etl["pipeline_run_id"] == "etl_teste"
    assert Path(resultado_etl["arquivo_manifesto"]).exists()
    assert manifesto_etl["staging"]["contratos"]["source_snapshot_id"] == "20260930_120000"
    assert manifesto_etl["curated"]["contratos_gastos"]["pipeline_run_id"] == "etl_teste"
    assert manifesto_etl["curated"]["quality"]["pipeline_run_id"] == "etl_teste"
