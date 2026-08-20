"""Publica indicadores financeiros anuais por fornecedor da camada curated."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STAGING_DIR = PROJECT_ROOT / "1.data" / "2.staging"
CURATED_DIR = PROJECT_ROOT / "1.data" / "3.curated"
EXCEPTIONS_DIR = CURATED_DIR / "exceptions"

ANOS_FINANCEIROS = range(2022, 2027)
MEDIDAS_FINANCEIRAS = {
    "faturamento": "gross_revenue",
    "custo": "total_cost",
    "custo_folha": "payroll_cost",
    "lucro_bruto": "gross_profit",
    "juros_divida": "debt_interest",
    "lucro_liquido": "net_income",
}
COLUNAS_LINHAGEM = ["source_file", "source_row_number", "load_date", "batch_id"]
COLUNAS_EMPRESAS = [
    "cnpj",
    *[f"{origem}_{ano}" for origem in MEDIDAS_FINANCEIRAS for ano in ANOS_FINANCEIROS],
    *COLUNAS_LINHAGEM,
]


def localizar_arquivo(tabela, identificador_lote, diretorio):
    arquivo = Path(diretorio) / f"{tabela}_{identificador_lote}.parquet"
    if not arquivo.exists():
        raise FileNotFoundError(f"Não foi encontrado {tabela} para o lote {identificador_lote}: {arquivo}.")
    return arquivo


def carregar_fontes(identificador_lote, staging_dir=STAGING_DIR, curated_dir=CURATED_DIR):
    """Carrega empresas tratadas e dimensões necessárias à resolução da fato."""
    arquivos = {
        "empresas": ("stg_empresas", staging_dir, COLUNAS_EMPRESAS),
        "fornecedores": (
            "dim_supplier",
            curated_dir,
            ["supplier_cnpj", "supplier_key", "economic_group_key"],
        ),
        "calendario": ("dim_calendar", curated_dir, ["calendar_date", "calendar_key"]),
    }
    fontes = {}
    for nome, (tabela, diretorio, colunas) in arquivos.items():
        try:
            fontes[nome] = pd.read_parquet(
                localizar_arquivo(tabela, identificador_lote, diretorio), columns=colunas
            )
        except Exception as erro:
            raise ValueError(f"Não foi possível carregar {nome}: {erro}") from erro
    return fontes


def adicionar_erro(erros, mascara, mensagem):
    erros.loc[mascara] = erros.loc[mascara].map(
        lambda atual: f"{atual}; {mensagem}" if atual else mensagem
    )


def explodir_indicadores_financeiros(empresas):
    """Transforma os indicadores anuais em uma linha por fornecedor e ano fiscal."""
    periodos = []
    for ano in ANOS_FINANCEIROS:
        periodo = empresas[["cnpj", *COLUNAS_LINHAGEM]].copy()
        periodo["financial_year"] = ano
        periodo["financial_period_end_date"] = date(ano, 12, 31)
        for origem, destino in MEDIDAS_FINANCEIRAS.items():
            periodo[destino] = pd.to_numeric(empresas[f"{origem}_{ano}"], errors="coerce")
        periodos.append(periodo)
    resultado = pd.concat(periodos, ignore_index=True)
    resultado["financial_snapshot_key"] = (
        "FIN-" + resultado["cnpj"].astype("string") + "-" + resultado["financial_year"].astype("string")
    )
    return resultado


def construir_fact_supplier_financial(fontes):
    """Resolve fatos anuais contra fornecedor e calendário, isolando exceções."""
    fatos = explodir_indicadores_financeiros(fontes["empresas"])
    fornecedores = fontes["fornecedores"].rename(
        columns={
            "supplier_key": "resolved_supplier_key",
            "economic_group_key": "resolved_economic_group_key",
        }
    )
    fatos = fatos.merge(
        fornecedores,
        left_on="cnpj",
        right_on="supplier_cnpj",
        how="left",
        validate="many_to_one",
    )
    chaves_calendario = fontes["calendario"].set_index("calendar_date")["calendar_key"]
    fatos["financial_period_calendar_key"] = fatos["financial_period_end_date"].map(chaves_calendario)

    erros = pd.Series("", index=fatos.index, dtype="string")
    adicionar_erro(
        erros,
        fatos["financial_snapshot_key"].duplicated(keep=False),
        "financial_snapshot_key duplicada na fonte curated",
    )
    adicionar_erro(erros, fatos["resolved_supplier_key"].isna(), "cnpj não encontrado em dim_supplier")
    adicionar_erro(
        erros,
        fatos["financial_period_calendar_key"].isna(),
        "financial_period_end_date não encontrado em dim_calendar",
    )
    for coluna in MEDIDAS_FINANCEIRAS.values():
        adicionar_erro(erros, fatos[coluna].isna(), f"{coluna} ausente ou inválida")
        adicionar_erro(erros, fatos[coluna].lt(0).fillna(False), f"{coluna} não pode ser negativa")
    adicionar_erro(
        erros,
        fatos["payroll_cost"].gt(fatos["total_cost"]).fillna(False),
        "payroll_cost maior que total_cost",
    )
    adicionar_erro(
        erros,
        fatos["total_cost"].gt(fatos["gross_revenue"]).fillna(False),
        "total_cost maior que gross_revenue",
    )
    adicionar_erro(
        erros,
        fatos["gross_profit"].gt(fatos["gross_revenue"]).fillna(False),
        "gross_profit maior que gross_revenue",
    )
    adicionar_erro(
        erros,
        fatos["net_income"].gt(fatos["gross_profit"]).fillna(False),
        "net_income maior que gross_profit",
    )

    fatos["curated_validation_errors"] = erros
    resolvidos = fatos.loc[erros.eq("")].copy()
    excecoes = fatos.loc[erros.ne("")].copy()
    resolvidos = resolvidos.rename(
        columns={
            "resolved_supplier_key": "supplier_key",
            "resolved_economic_group_key": "economic_group_key",
        }
    )
    colunas = [
        "financial_snapshot_key",
        "supplier_key",
        "economic_group_key",
        "financial_period_calendar_key",
        "financial_year",
        *MEDIDAS_FINANCEIRAS.values(),
        *COLUNAS_LINHAGEM,
    ]
    return resolvidos[colunas], excecoes


def construir_cobertura(empresas, fato, excecoes):
    """Comprova que cada combinação fornecedor-ano foi publicada ou explicada."""
    esperados = len(empresas) * len(ANOS_FINANCEIROS)
    return {
        "source_row_count": esperados,
        "fact_row_count": len(fato),
        "exception_row_count": len(excecoes),
        "is_reconciled": esperados == len(fato) + len(excecoes),
    }


def executar_publicacao(
    identificador_lote,
    staging_dir=STAGING_DIR,
    curated_dir=CURATED_DIR,
    exceptions_dir=EXCEPTIONS_DIR,
):
    """Publica a fato financeira anual e suas exceções para um lote curated."""
    fontes = carregar_fontes(identificador_lote, staging_dir, curated_dir)
    fato, excecoes = construir_fact_supplier_financial(fontes)
    cobertura = construir_cobertura(fontes["empresas"], fato, excecoes)
    if not cobertura["is_reconciled"]:
        raise ValueError("A cobertura entre stg_empresas, fato financeira e exceções falhou.")

    curated_dir = Path(curated_dir)
    exceptions_dir = Path(exceptions_dir)
    curated_dir.mkdir(parents=True, exist_ok=True)
    exceptions_dir.mkdir(parents=True, exist_ok=True)
    arquivo_fato = curated_dir / f"fact_supplier_financial_{identificador_lote}.parquet"
    arquivo_excecoes = exceptions_dir / f"fact_supplier_financial_exceptions_{identificador_lote}.parquet"
    fato.to_parquet(arquivo_fato, index=False)
    excecoes.to_parquet(arquivo_excecoes, index=False)

    print(f"Indicadores financeiros publicados: {len(fato)}")
    print(f"Indicadores financeiros com exceção: {len(excecoes)}")
    return {
        "arquivo_fact_supplier_financial": arquivo_fato,
        "arquivo_excecoes": arquivo_excecoes,
        "indicadores_publicados": len(fato),
        "indicadores_invalidos": len(excecoes),
        "manifesto": {
            "batch_id": identificador_lote,
            "tables": {"fact_supplier_financial": {"row_count": len(fato)}},
            "financial_coverage": cobertura,
        },
    }


if __name__ == "__main__":
    arquivo = max(STAGING_DIR.glob("stg_empresas_*.parquet"))
    executar_publicacao(arquivo.stem.removeprefix("stg_empresas_"))
