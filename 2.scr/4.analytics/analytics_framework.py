"""Utilitários de contrato para a camada analítica DuckDB."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

ARTEFATOS_CURATED = {
    "dim_supplier": "dim_supplier_{snapshot_id}.parquet",
    "dim_economic_group": "dim_economic_group_{snapshot_id}.parquet",
    "dim_calendar": "dim_calendar_{snapshot_id}.parquet",
    "dim_category": "dim_category_{snapshot_id}.parquet",
    "dim_contract": "dim_contract_{snapshot_id}.parquet",
    "fact_spending": "fact_spending_{snapshot_id}.parquet",
    "fact_renewal": "fact_renewal_{snapshot_id}.parquet",
    "quality_reconciliation": "curated_reconciliation_report_{snapshot_id}.parquet",
    "quality_exceptions": "curated_exception_index_{snapshot_id}.parquet",
}


class AnalyticsContractError(ValueError):
    """Indica um manifesto ETL ou artefato curated impróprio para consumo."""


@dataclass(frozen=True)
class AnalyticsInput:
    """Contexto imutável de uma execução analítica."""

    etl_manifest_path: Path
    pipeline_run_id: str
    source_snapshot_id: str
    scenario_id: str
    curated_dir: Path
    artifacts: dict[str, Path]


def carregar_entrada(caminho_manifesto):
    """Valida o handoff ETL e resolve somente os Parquets curated declarados."""
    caminho_manifesto = Path(caminho_manifesto)
    dados = json.loads(caminho_manifesto.read_text(encoding="utf-8"))
    campos = {"pipeline_run_id", "source_snapshot_id", "scenario_id", "directories", "curated"}
    ausentes = campos.difference(dados)
    if ausentes:
        raise AnalyticsContractError(f"Manifesto ETL sem campos obrigatórios: {', '.join(sorted(ausentes))}.")
    if not dados["curated"].get("quality", {}).get("quality_passed"):
        raise AnalyticsContractError("O quality gate curated não foi aprovado para este pipeline run.")
    curated_dir = Path(dados["directories"].get("curated", ""))
    if not curated_dir.is_dir():
        raise AnalyticsContractError(f"Diretório curated inexistente: {curated_dir}.")
    snapshot_id = str(dados["source_snapshot_id"])
    artifacts = {
        nome: curated_dir / padrao.format(snapshot_id=snapshot_id)
        for nome, padrao in ARTEFATOS_CURATED.items()
    }
    ausentes = [str(arquivo) for arquivo in artifacts.values() if not arquivo.is_file()]
    if ausentes:
        raise AnalyticsContractError(f"Artefatos curated ausentes: {', '.join(ausentes)}.")
    return AnalyticsInput(
        etl_manifest_path=caminho_manifesto,
        pipeline_run_id=str(dados["pipeline_run_id"]),
        source_snapshot_id=snapshot_id,
        scenario_id=str(dados["scenario_id"]),
        curated_dir=curated_dir,
        artifacts=artifacts,
    )


def caminho_banco_padrao(entrada):
    """Deriva um banco local isolado a partir do diretório `1.data`."""
    data_dir = entrada.etl_manifest_path.parents[2]
    return data_dir / "4.analytics" / entrada.pipeline_run_id / "contract_analytics.duckdb"


def literal_sql(valor):
    """Converte um caminho ou texto em literal SQL DuckDB seguro."""
    return "'" + str(valor).replace("'", "''") + "'"


def criar_views_de_fonte(conexao, entrada):
    """Expõe Parquets curated como fontes internas das views analíticas."""
    for nome, arquivo in entrada.artifacts.items():
        conexao.execute(
            f"CREATE OR REPLACE VIEW src_{nome} AS "
            f"SELECT * FROM read_parquet({literal_sql(arquivo.as_posix())});"
        )


def registrar_contexto(conexao, entrada):
    """Registra a linhagem do banco, sem misturá-la às views de negócio."""
    conexao.execute(
        """
        CREATE TABLE IF NOT EXISTS analytics_run_context (
            pipeline_run_id VARCHAR PRIMARY KEY,
            source_snapshot_id VARCHAR NOT NULL,
            scenario_id VARCHAR NOT NULL,
            etl_manifest_path VARCHAR NOT NULL,
            curated_dir VARCHAR NOT NULL
        )
        """
    )
    conexao.execute("DELETE FROM analytics_run_context")
    conexao.execute(
        "INSERT INTO analytics_run_context VALUES (?, ?, ?, ?, ?)",
        [
            entrada.pipeline_run_id,
            entrada.source_snapshot_id,
            entrada.scenario_id,
            str(entrada.etl_manifest_path),
            str(entrada.curated_dir),
        ],
    )
