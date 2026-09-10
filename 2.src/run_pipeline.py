"""Atalho retrocompatível: gera um snapshot inicial e executa seu ETL."""

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
RAW_DIR = PROJECT_ROOT / "1.data" / "1.raw"
STAGING_DIR = PROJECT_ROOT / "1.data" / "2.staging"
CURATED_DIR = PROJECT_ROOT / "1.data" / "3.curated"
sys.path.insert(0, str(SCRIPT_DIR))

from generate_raw import RawGenerationConfig, gerar_snapshot_inicial
from generate_raw import validar_config as validar_raw
from run_etl import executar_etl

TIMEZONE = ZoneInfo("America/Sao_Paulo")


@dataclass
class PipelineConfig:
    """Parâmetros do atalho para um cenário RAW inicial reproduzível."""

    qtd_empresas: int = 300
    seed: int | None = None
    data_referencia: date = field(default_factory=lambda: datetime.now(TIMEZONE).date())
    percentual_matrizes_grandes_com_filiais: float = 0.50
    probabilidade_outlier: float = 0.10
    probabilidade_aporte: float = 0.35
    probabilidade_outlier_qtd_contratos: float = 0.12
    limite_exposicao_normal_min: float = 0.20
    limite_exposicao_normal_max: float = 0.45
    limite_exposicao_outlier_min: float = 0.45
    limite_exposicao_outlier_max: float = 0.90
    min_curated_match_rate: float = 0.95
    financial_reconciliation_tolerance: float = 0.0


def converter_data(valor):
    return valor if isinstance(valor, date) else date.fromisoformat(valor)


def _config_raw(config, scenario_id):
    return RawGenerationConfig(
        scenario_id=scenario_id,
        qtd_empresas=config.qtd_empresas,
        seed=config.seed,
        data_referencia=config.data_referencia,
        percentual_matrizes_grandes_com_filiais=config.percentual_matrizes_grandes_com_filiais,
        probabilidade_outlier=config.probabilidade_outlier,
        probabilidade_aporte=config.probabilidade_aporte,
        probabilidade_outlier_qtd_contratos=config.probabilidade_outlier_qtd_contratos,
        limite_exposicao_normal_min=config.limite_exposicao_normal_min,
        limite_exposicao_normal_max=config.limite_exposicao_normal_max,
        limite_exposicao_outlier_min=config.limite_exposicao_outlier_min,
        limite_exposicao_outlier_max=config.limite_exposicao_outlier_max,
    )


def validar_config(config):
    validar_raw(_config_raw(config, "pipeline_legacy"))
    if not 0 <= config.min_curated_match_rate <= 1:
        raise ValueError("min_curated_match_rate deve estar entre 0 e 1.")
    if config.financial_reconciliation_tolerance < 0:
        raise ValueError("A tolerância financeira não pode ser negativa.")


def executar_pipeline(
    config,
    raw_dir=RAW_DIR,
    staging_dir=STAGING_DIR,
    exceptions_dir=None,
    curated_dir=CURATED_DIR,
    curated_exceptions_dir=None,
    identificador_lote=None,
):
    """Executa ``generate_raw`` seguido de ``run_etl`` para um novo cenário."""
    validar_config(config)
    snapshot_id = identificador_lote or datetime.now(TIMEZONE).strftime("%Y%m%d_%H%M%S")
    scenario_id = f"pipeline_{snapshot_id}"
    raw = gerar_snapshot_inicial(_config_raw(config, scenario_id), raw_dir, snapshot_id)
    etl = executar_etl(
        raw["arquivo_manifesto"],
        pipeline_run_id=f"legacy_{snapshot_id}",
        staging_root=staging_dir,
        curated_root=curated_dir,
        min_curated_match_rate=config.min_curated_match_rate,
        financial_reconciliation_tolerance=config.financial_reconciliation_tolerance,
    )
    return {
        "identificador_lote": snapshot_id,
        "arquivo_manifesto_raw": raw["arquivo_manifesto"],
        "arquivo_manifesto_etl": etl["arquivo_manifesto"],
        "raw": raw["manifesto"],
        "etl": etl["manifesto"],
    }


def carregar_config(caminho):
    dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
    if "data_referencia" in dados:
        dados["data_referencia"] = converter_data(dados["data_referencia"])
    return PipelineConfig(**dados)


def criar_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", help="Caminho para configuração JSON.")
    parser.add_argument("--qtd-empresas", type=int)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--data-referencia")
    return parser


def main():
    argumentos = criar_parser().parse_args()
    config = carregar_config(argumentos.config) if argumentos.config else PipelineConfig()
    for campo, valor in {"qtd_empresas": argumentos.qtd_empresas, "seed": argumentos.seed}.items():
        if valor is not None:
            setattr(config, campo, valor)
    if argumentos.data_referencia:
        config.data_referencia = converter_data(argumentos.data_referencia)
    resultado = executar_pipeline(config)
    print(f"Manifesto RAW: {resultado['arquivo_manifesto_raw']}")
    print(f"Manifesto ETL: {resultado['arquivo_manifesto_etl']}")


if __name__ == "__main__":
    main()
