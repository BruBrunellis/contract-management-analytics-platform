"""Orquestra a geração das fontes primárias e a staging de empresas."""

import argparse
import json
import random
import sys
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
RAW_DIR = PROJECT_ROOT / "1.data" / "1.raw"
STAGING_DIR = PROJECT_ROOT / "1.data" / "2.staging"
EXCEPTIONS_DIR = STAGING_DIR / "exceptions"
GENERATOR_DIR = SCRIPT_DIR / "1.generator"
ETL_DIR = SCRIPT_DIR / "2.etl"
CURATED_SCRIPT_DIR = SCRIPT_DIR / "3.curated"
CURATED_DIR = PROJECT_ROOT / "1.data" / "3.curated"
CURATED_EXCEPTIONS_DIR = CURATED_DIR / "exceptions"
TIMEZONE = ZoneInfo("America/Sao_Paulo")

sys.path.insert(0, str(GENERATOR_DIR))
sys.path.insert(0, str(ETL_DIR))
sys.path.insert(0, str(CURATED_SCRIPT_DIR))

import company_generator
import contract_generator
import dim_calendario_categoria
import dim_contratos_gastos
import dim_fornecedores
import risk_generator
import spending_generator
import stg_aditamentos
import stg_contratos
import stg_empresas
import stg_homologacoes_risco
import stg_pagamentos


@dataclass
class PipelineConfig:
    """Parâmetros reproduzíveis de uma execução completa."""

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


def converter_data(valor):
    """Converte uma data ISO para o tipo usado pelos geradores."""
    if isinstance(valor, date):
        return valor
    return date.fromisoformat(valor)


def validar_config(config):
    """Valida parâmetros antes de criar arquivos."""
    if config.qtd_empresas <= 0:
        raise ValueError("qtd_empresas deve ser positiva.")
    probabilidades = {
        "percentual_matrizes_grandes_com_filiais": config.percentual_matrizes_grandes_com_filiais,
        "probabilidade_outlier": config.probabilidade_outlier,
        "probabilidade_aporte": config.probabilidade_aporte,
        "probabilidade_outlier_qtd_contratos": config.probabilidade_outlier_qtd_contratos,
        "limite_exposicao_normal_min": config.limite_exposicao_normal_min,
        "limite_exposicao_normal_max": config.limite_exposicao_normal_max,
        "limite_exposicao_outlier_min": config.limite_exposicao_outlier_min,
        "limite_exposicao_outlier_max": config.limite_exposicao_outlier_max,
    }
    for nome, valor in probabilidades.items():
        if not 0 <= valor <= 1:
            raise ValueError(f"{nome} deve estar entre 0 e 1.")
    if config.limite_exposicao_normal_min > config.limite_exposicao_normal_max:
        raise ValueError("O limite normal mínimo não pode superar o máximo.")
    if config.limite_exposicao_outlier_min > config.limite_exposicao_outlier_max:
        raise ValueError("O limite outlier mínimo não pode superar o máximo.")


def executar_pipeline(
    config,
    raw_dir=RAW_DIR,
    staging_dir=STAGING_DIR,
    exceptions_dir=EXCEPTIONS_DIR,
    curated_dir=CURATED_DIR,
    curated_exceptions_dir=CURATED_EXCEPTIONS_DIR,
    identificador_lote=None,
):
    """Executa todas as etapas usando o mesmo lote e os mesmos parâmetros."""
    validar_config(config)
    if config.seed is not None:
        random.seed(config.seed)

    identificador_lote = identificador_lote or datetime.now(TIMEZONE).strftime("%Y%m%d_%H%M%S")
    raw_dir.mkdir(parents=True, exist_ok=True)

    empresas = company_generator.gerar_tabela_empresas(
        config.qtd_empresas,
        config.percentual_matrizes_grandes_com_filiais,
    )
    arquivo_empresas = raw_dir / f"empresas_{identificador_lote}.csv"
    empresas.to_csv(arquivo_empresas, index=False, encoding="utf-8-sig")

    riscos = risk_generator.gerar_homologacoes_risco(empresas, config.data_referencia)
    arquivo_riscos = raw_dir / f"homologacoes_risco_{identificador_lote}.csv"
    riscos.to_csv(arquivo_riscos, index=False, encoding="utf-8-sig")

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
    arquivo_contratos = raw_dir / f"contratos_ficticios_{identificador_lote}.csv"
    arquivo_aditamentos = raw_dir / f"aditamentos_{identificador_lote}.csv"
    contratos.to_csv(arquivo_contratos, index=False, encoding="utf-8-sig")
    aditamentos.to_csv(arquivo_aditamentos, index=False, encoding="utf-8-sig")

    spending = spending_generator.gerar_tabela_spending(
        contratos,
        aditamentos,
        config.data_referencia,
        config.data_referencia,
    )
    arquivo_spending = raw_dir / f"spending_ficticio_{identificador_lote}.csv"
    spending.to_csv(arquivo_spending, index=False, encoding="utf-8-sig")

    resultado_staging = stg_empresas.executar_staging(
        arquivo_empresas,
        identificador_lote,
        config.data_referencia,
        staging_dir,
        exceptions_dir,
    )
    resultado_curated_fornecedores = dim_fornecedores.executar_publicacao(
        resultado_staging["arquivo_staging"],
        identificador_lote,
        curated_dir,
        curated_exceptions_dir,
    )
    resultado_staging_riscos = stg_homologacoes_risco.executar_staging(
        arquivo_riscos,
        identificador_lote,
        config.data_referencia,
        staging_dir,
        exceptions_dir,
    )
    resultado_staging_contratos = stg_contratos.executar_staging(
        arquivo_contratos,
        identificador_lote,
        config.data_referencia,
        staging_dir,
        exceptions_dir,
    )
    resultado_staging_aditamentos = stg_aditamentos.executar_staging(
        arquivo_aditamentos,
        identificador_lote,
        config.data_referencia,
        staging_dir,
        exceptions_dir,
        resultado_staging_contratos["arquivo_staging"],
    )
    resultado_staging_pagamentos = stg_pagamentos.executar_staging(
        arquivo_spending,
        identificador_lote,
        config.data_referencia,
        staging_dir,
        exceptions_dir,
        resultado_staging_contratos["arquivo_staging"],
    )
    resultado_curated_compartilhadas = dim_calendario_categoria.executar_publicacao(
        identificador_lote,
        staging_dir,
        curated_dir,
    )
    resultado_curated_contratos_gastos = dim_contratos_gastos.executar_publicacao(
        identificador_lote,
        staging_dir,
        curated_dir,
        curated_exceptions_dir,
    )

    manifesto = {
        "identificador_lote": identificador_lote,
        "data_referencia": config.data_referencia.isoformat(),
        "parametros": {**asdict(config), "data_referencia": config.data_referencia.isoformat()},
        "arquivos": {
            "empresas": str(arquivo_empresas),
            "riscos": str(arquivo_riscos),
            "contratos": str(arquivo_contratos),
            "aditamentos": str(arquivo_aditamentos),
            "spending": str(arquivo_spending),
            "stg_empresas": str(resultado_staging["arquivo_staging"]),
            "stg_empresas_invalidas": str(resultado_staging["arquivo_excecoes"]),
            "dim_supplier": str(resultado_curated_fornecedores["arquivo_dim_supplier"]),
            "dim_economic_group": str(resultado_curated_fornecedores["arquivo_dim_economic_group"]),
            "dim_supplier_resolution_exceptions": str(resultado_curated_fornecedores["arquivo_excecoes"]),
            "dim_calendar": str(resultado_curated_compartilhadas["arquivo_dim_calendar"]),
            "dim_category": str(resultado_curated_compartilhadas["arquivo_dim_category"]),
            "dim_contract": str(resultado_curated_contratos_gastos["arquivo_dim_contract"]),
            "fact_spending": str(resultado_curated_contratos_gastos["arquivo_fact_spending"]),
            "dim_contract_resolution_exceptions": str(resultado_curated_contratos_gastos["arquivo_excecoes_contratos"]),
            "fact_spending_exceptions": str(resultado_curated_contratos_gastos["arquivo_excecoes_pagamentos"]),
            "stg_homologacoes_risco": str(resultado_staging_riscos["arquivo_staging"]),
            "stg_homologacoes_risco_invalidas": str(resultado_staging_riscos["arquivo_excecoes"]),
            "stg_contratos": str(resultado_staging_contratos["arquivo_staging"]),
            "stg_contratos_invalidos": str(resultado_staging_contratos["arquivo_excecoes"]),
            "stg_aditamentos": str(resultado_staging_aditamentos["arquivo_staging"]),
            "stg_aditamentos_invalidos": str(resultado_staging_aditamentos["arquivo_excecoes"]),
            "stg_pagamentos": str(resultado_staging_pagamentos["arquivo_staging"]),
            "stg_pagamentos_invalidos": str(resultado_staging_pagamentos["arquivo_excecoes"]),
        },
        "contagens": {
            "empresas": len(empresas),
            "riscos": len(riscos),
            "contratos": len(contratos),
            "aditamentos": len(aditamentos),
            "pagamentos": len(spending),
            "stg_empresas_validas": resultado_staging["registros_validos"],
            "stg_empresas_invalidas": resultado_staging["registros_invalidos"],
            "dim_supplier": resultado_curated_fornecedores["fornecedores_publicados"],
            "dim_economic_group": resultado_curated_fornecedores["grupos_publicados"],
            "dim_supplier_resolution_exceptions": resultado_curated_fornecedores["registros_invalidos"],
            "dim_calendar": resultado_curated_compartilhadas["dias_publicados"],
            "dim_category": resultado_curated_compartilhadas["categorias_publicadas"],
            "dim_contract": resultado_curated_contratos_gastos["contratos_publicados"],
            "dim_contract_resolution_exceptions": resultado_curated_contratos_gastos["contratos_invalidos"],
            "fact_spending": resultado_curated_contratos_gastos["pagamentos_publicados"],
            "fact_spending_exceptions": resultado_curated_contratos_gastos["pagamentos_invalidos"],
            "stg_homologacoes_risco_validas": resultado_staging_riscos["registros_validos"],
            "stg_homologacoes_risco_invalidas": resultado_staging_riscos["registros_invalidos"],
            "stg_contratos_validos": resultado_staging_contratos["registros_validos"],
            "stg_contratos_invalidos": resultado_staging_contratos["registros_invalidos"],
            "stg_aditamentos_validos": resultado_staging_aditamentos["registros_validos"],
            "stg_aditamentos_invalidos": resultado_staging_aditamentos["registros_invalidos"],
            "stg_pagamentos_validos": resultado_staging_pagamentos["registros_validos"],
            "stg_pagamentos_invalidos": resultado_staging_pagamentos["registros_invalidos"],
        },
        "staging": {
            "empresas": resultado_staging["manifesto"],
            "homologacoes_risco": resultado_staging_riscos["manifesto"],
            "contratos": resultado_staging_contratos["manifesto"],
            "aditamentos": resultado_staging_aditamentos["manifesto"],
            "pagamentos": resultado_staging_pagamentos["manifesto"],
        },
        "curated": {
            "fornecedores": resultado_curated_fornecedores["manifesto"],
            "compartilhadas": resultado_curated_compartilhadas["manifesto"],
            "contratos_gastos": resultado_curated_contratos_gastos["manifesto"],
        },
    }
    arquivo_manifesto = raw_dir / f"run_manifest_{identificador_lote}.json"
    arquivo_manifesto.write_text(
        json.dumps(manifesto, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    manifesto["arquivos"]["manifesto"] = str(arquivo_manifesto)
    return manifesto


def carregar_config(caminho):
    """Carrega os parâmetros de uma configuração JSON."""
    dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
    if "data_referencia" in dados:
        dados["data_referencia"] = converter_data(dados["data_referencia"])
    return PipelineConfig(**dados)


def solicitar_valor(mensagem, padrao, conversor):
    resposta = input(f"{mensagem} [{padrao}]: ").strip()
    return padrao if not resposta else conversor(resposta)


def configurar_interativamente(config):
    """Solicita os parâmetros principais sem sacrificar a execução automatizável."""
    config.qtd_empresas = solicitar_valor("Quantidade de empresas", config.qtd_empresas, int)
    resposta_seed = input(f"Seed aleatória (vazio mantém {config.seed}): ").strip()
    if resposta_seed:
        config.seed = int(resposta_seed)
    config.data_referencia = solicitar_valor(
        "Data de referência (AAAA-MM-DD)", config.data_referencia.isoformat(), converter_data
    )
    config.percentual_matrizes_grandes_com_filiais = solicitar_valor(
        "Percentual de matrizes grandes com filiais", config.percentual_matrizes_grandes_com_filiais, float
    )
    config.probabilidade_outlier = solicitar_valor(
        "Probabilidade global de outlier", config.probabilidade_outlier, float
    )
    config.probabilidade_aporte = solicitar_valor(
        "Probabilidade de aporte", config.probabilidade_aporte, float
    )
    return config


def criar_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", help="Caminho para um arquivo JSON de parâmetros.")
    parser.add_argument("--interactive", action="store_true", help="Solicita os parâmetros no terminal.")
    parser.add_argument("--qtd-empresas", type=int)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--data-referencia")
    parser.add_argument("--percentual-filiais", type=float)
    parser.add_argument("--probabilidade-outlier", type=float)
    parser.add_argument("--probabilidade-aporte", type=float)
    parser.add_argument("--probabilidade-outlier-qtd-contratos", type=float)
    return parser


def config_por_argumentos(argumentos):
    config = carregar_config(argumentos.config) if argumentos.config else PipelineConfig()
    campos = {
        "qtd_empresas": argumentos.qtd_empresas,
        "seed": argumentos.seed,
        "percentual_matrizes_grandes_com_filiais": argumentos.percentual_filiais,
        "probabilidade_outlier": argumentos.probabilidade_outlier,
        "probabilidade_aporte": argumentos.probabilidade_aporte,
        "probabilidade_outlier_qtd_contratos": argumentos.probabilidade_outlier_qtd_contratos,
    }
    for campo, valor in campos.items():
        if valor is not None:
            setattr(config, campo, valor)
    if argumentos.data_referencia:
        config.data_referencia = converter_data(argumentos.data_referencia)
    return configurar_interativamente(config) if argumentos.interactive else config


def main():
    argumentos = criar_parser().parse_args()
    config = config_por_argumentos(argumentos)
    manifesto = executar_pipeline(config)
    print(f"Lote concluído: {manifesto['identificador_lote']}")
    print(f"Manifesto: {manifesto['arquivos']['manifesto']}")


if __name__ == "__main__":
    main()
