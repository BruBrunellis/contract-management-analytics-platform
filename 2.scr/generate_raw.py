"""Gera o snapshot RAW inicial e um manifesto de cenário reproduzível."""

from __future__ import annotations

import argparse
import random
import sys
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
RAW_DIR = PROJECT_ROOT / "1.data" / "1.raw"
GENERATOR_DIR = SCRIPT_DIR / "1.generator"
sys.path.insert(0, str(GENERATOR_DIR))

import company_generator
import contract_generator
import risk_generator
import spending_generator
from raw_snapshot_framework import gravar_snapshot, novo_snapshot_id

TIMEZONE = ZoneInfo("America/Sao_Paulo")


@dataclass
class RawGenerationConfig:
    scenario_id: str
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


def validar_config(config):
    if not config.scenario_id.strip():
        raise ValueError("scenario_id é obrigatório.")
    if config.qtd_empresas <= 0:
        raise ValueError("qtd_empresas deve ser positiva.")
    for nome in [
        "percentual_matrizes_grandes_com_filiais",
        "probabilidade_outlier",
        "probabilidade_aporte",
        "probabilidade_outlier_qtd_contratos",
        "limite_exposicao_normal_min",
        "limite_exposicao_normal_max",
        "limite_exposicao_outlier_min",
        "limite_exposicao_outlier_max",
    ]:
        if not 0 <= getattr(config, nome) <= 1:
            raise ValueError(f"{nome} deve estar entre 0 e 1.")


def gerar_snapshot_inicial(config, raw_dir=RAW_DIR, snapshot_id=None):
    """Gera fontes completas e coerentes de um cenário inicial."""
    validar_config(config)
    if config.seed is not None:
        random.seed(config.seed)
    snapshot_id = novo_snapshot_id(snapshot_id)
    empresas = company_generator.gerar_tabela_empresas(
        config.qtd_empresas, config.percentual_matrizes_grandes_com_filiais
    )
    riscos = risk_generator.gerar_homologacoes_risco(empresas, config.data_referencia)
    contratos, aditamentos = contract_generator.gerar_tabelas_contratos(
        empresas,
        riscos,
        config.data_referencia,
        config.probabilidade_outlier,
        config.probabilidade_aporte,
        config.probabilidade_outlier_qtd_contratos,
        (config.limite_exposicao_normal_min, config.limite_exposicao_normal_max),
        (config.limite_exposicao_outlier_min, config.limite_exposicao_outlier_max),
    )
    pagamentos = spending_generator.gerar_tabela_spending(
        contratos, aditamentos, config.data_referencia, config.data_referencia
    )
    parametros = asdict(config)
    parametros["data_referencia"] = config.data_referencia.isoformat()
    arquivo_manifesto, manifesto = gravar_snapshot(
        {
            "empresas": empresas,
            "homologacoes_risco": riscos,
            "contratos": contratos,
            "aditamentos": aditamentos,
            "pagamentos": pagamentos,
        },
        raw_dir=raw_dir,
        scenario_id=config.scenario_id,
        snapshot_id=snapshot_id,
        data_referencia=config.data_referencia,
        parametros=parametros,
    )
    return {"arquivo_manifesto": arquivo_manifesto, "manifesto": manifesto}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario-id", required=True)
    parser.add_argument("--qtd-empresas", type=int, default=300)
    parser.add_argument("--seed", type=int)
    parser.add_argument(
        "--data-referencia", type=date.fromisoformat, default=datetime.now(TIMEZONE).date()
    )
    argumentos = parser.parse_args()
    resultado = gerar_snapshot_inicial(
        RawGenerationConfig(
            scenario_id=argumentos.scenario_id,
            qtd_empresas=argumentos.qtd_empresas,
            seed=argumentos.seed,
            data_referencia=argumentos.data_referencia,
        )
    )
    print(f"Manifesto RAW: {resultado['arquivo_manifesto']}")


if __name__ == "__main__":
    main()
