"""Executa STAGING e CURATED a partir de um manifesto RAW explícito."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DATA_DIR = PROJECT_ROOT / "1.data"
ETL_DIR = SCRIPT_DIR / "2.etl"
CURATED_SCRIPT_DIR = SCRIPT_DIR / "3.curated"
sys.path.insert(0, str(ETL_DIR))
sys.path.insert(0, str(CURATED_SCRIPT_DIR))

import dim_calendario_categoria
import dim_contratos_gastos
import dim_fornecedores
import fact_fornecedor_financeiro
import facts_risco_renovacao
import reconciliacoes_curated
import stg_aditamentos
import stg_contratos
import stg_empresas
import stg_homologacoes_risco
import stg_pagamentos
from raw_snapshot_framework import carregar_manifesto

TIMEZONE = ZoneInfo("America/Sao_Paulo")


def novo_pipeline_run_id(snapshot_id):
    return f"{snapshot_id}_etl_{datetime.now(TIMEZONE).strftime('%Y%m%d_%H%M%S')}"


def registrar_contexto(resultado, source_snapshot_id, pipeline_run_id):
    """Acrescenta o contexto da execução aos manifestos de cada etapa."""
    resultado["manifesto"]["source_snapshot_id"] = source_snapshot_id
    resultado["manifesto"]["pipeline_run_id"] = pipeline_run_id
    return resultado


def executar_etl(
    caminho_manifesto,
    *,
    data_dir=DATA_DIR,
    staging_root=None,
    curated_root=None,
    pipeline_run_id=None,
    min_curated_match_rate=0.95,
    financial_reconciliation_tolerance=0.0,
):
    """Materializa um processamento isolado a partir das fontes do manifesto."""
    caminho_manifesto = Path(caminho_manifesto)
    raw_manifest = carregar_manifesto(caminho_manifesto)
    snapshot_id = raw_manifest["snapshot_id"]
    pipeline_run_id = pipeline_run_id or novo_pipeline_run_id(snapshot_id)
    data_dir = Path(data_dir)
    staging_root = Path(staging_root) if staging_root else data_dir / "2.staging"
    curated_root = Path(curated_root) if curated_root else data_dir / "3.curated"
    staging_dir = staging_root / pipeline_run_id
    staging_exceptions_dir = staging_dir / "exceptions"
    curated_dir = curated_root / pipeline_run_id
    curated_exceptions_dir = curated_dir / "exceptions"
    if staging_dir.exists() or curated_dir.exists():
        raise FileExistsError(f"pipeline_run_id já possui artefatos: {pipeline_run_id}.")
    fontes = {
        nome: caminho_manifesto.parent / metadados["path"]
        for nome, metadados in raw_manifest["sources"].items()
    }
    data_referencia = date.fromisoformat(raw_manifest["as_of_date"])

    empresas = stg_empresas.executar_staging(
        fontes["empresas"], snapshot_id, data_referencia, staging_dir, staging_exceptions_dir
    )
    fornecedores = dim_fornecedores.executar_publicacao(
        empresas["arquivo_staging"], snapshot_id, curated_dir, curated_exceptions_dir
    )
    riscos = stg_homologacoes_risco.executar_staging(
        fontes["homologacoes_risco"], snapshot_id, data_referencia, staging_dir, staging_exceptions_dir
    )
    contratos = stg_contratos.executar_staging(
        fontes["contratos"], snapshot_id, data_referencia, staging_dir, staging_exceptions_dir
    )
    aditamentos = stg_aditamentos.executar_staging(
        fontes["aditamentos"], snapshot_id, data_referencia, staging_dir, staging_exceptions_dir,
        contratos["arquivo_staging"],
    )
    pagamentos = stg_pagamentos.executar_staging(
        fontes["pagamentos"], snapshot_id, data_referencia, staging_dir, staging_exceptions_dir,
        contratos["arquivo_staging"],
    )
    compartilhadas = dim_calendario_categoria.executar_publicacao(snapshot_id, staging_dir, curated_dir)
    financeiro_fornecedores = fact_fornecedor_financeiro.executar_publicacao(
        snapshot_id, staging_dir, curated_dir, curated_exceptions_dir
    )
    contratos_gastos = dim_contratos_gastos.executar_publicacao(
        snapshot_id, staging_dir, curated_dir, curated_exceptions_dir
    )
    risco_renovacao = facts_risco_renovacao.executar_publicacao(
        snapshot_id, staging_dir, curated_dir, curated_exceptions_dir
    )
    qualidade = reconciliacoes_curated.executar_reconciliacoes(
        snapshot_id,
        staging_dir,
        curated_dir,
        curated_exceptions_dir,
        min_curated_match_rate,
        financial_reconciliation_tolerance,
        pipeline_run_id=pipeline_run_id,
    )
    for resultado in [
        empresas,
        riscos,
        contratos,
        aditamentos,
        pagamentos,
        fornecedores,
        compartilhadas,
        financeiro_fornecedores,
        contratos_gastos,
        risco_renovacao,
    ]:
        registrar_contexto(resultado, snapshot_id, pipeline_run_id)
    manifesto = {
        "pipeline_run_id": pipeline_run_id,
        "source_snapshot_id": snapshot_id,
        "scenario_id": raw_manifest["scenario_id"],
        "raw_manifest": str(caminho_manifesto),
        "as_of_date": raw_manifest["as_of_date"],
        "directories": {"staging": str(staging_dir), "curated": str(curated_dir)},
        "staging": {
            "empresas": empresas["manifesto"],
            "homologacoes_risco": riscos["manifesto"],
            "contratos": contratos["manifesto"],
            "aditamentos": aditamentos["manifesto"],
            "pagamentos": pagamentos["manifesto"],
        },
        "curated": {
            "fornecedores": fornecedores["manifesto"],
            "compartilhadas": compartilhadas["manifesto"],
            "financeiro_fornecedores": financeiro_fornecedores["manifesto"],
            "contratos_gastos": contratos_gastos["manifesto"],
            "risco_renovacao": risco_renovacao["manifesto"],
            "quality": qualidade["manifesto"],
        },
    }
    arquivo_manifesto = curated_dir / "etl_manifest.json"
    arquivo_manifesto.parent.mkdir(parents=True, exist_ok=True)
    arquivo_manifesto.write_text(json.dumps(manifesto, ensure_ascii=False, indent=2), encoding="utf-8")
    if not qualidade["quality_passed"]:
        entidades = ", ".join(qualidade["entidades_reprovadas"])
        raise reconciliacoes_curated.CuratedQualityError(
            f"Quality gate reprovado para {pipeline_run_id}: {entidades}."
        )
    return {"arquivo_manifesto": arquivo_manifesto, "manifesto": manifesto}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-manifest", required=True)
    parser.add_argument("--pipeline-run-id")
    argumentos = parser.parse_args()
    resultado = executar_etl(argumentos.raw_manifest, pipeline_run_id=argumentos.pipeline_run_id)
    print(f"Manifesto ETL: {resultado['arquivo_manifesto']}")


if __name__ == "__main__":
    main()
