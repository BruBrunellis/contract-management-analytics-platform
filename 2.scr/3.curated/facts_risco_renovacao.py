"""Publica fatos curated de homologação/risco e de aditamentos contratuais."""

from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STAGING_DIR = PROJECT_ROOT / "1.data" / "2.staging"
CURATED_DIR = PROJECT_ROOT / "1.data" / "3.curated"
EXCEPTIONS_DIR = CURATED_DIR / "exceptions"

COLUNAS_RISCO = [
    "risk_assessment_id",
    "supplier_cnpj",
    "assessment_date",
    "last_approval_date",
    "expiration_date",
    "homologation_result",
    "homologation_status",
    "financial_risk",
    "labor_risk",
    "credit_rating",
    "final_risk",
    "interest_to_revenue_ratio",
    "revenue_trend",
    "net_margin",
    "labor_cases_index",
    "source_file",
    "source_row_number",
    "load_date",
    "batch_id",
]
COLUNAS_ADITAMENTOS = [
    "amendment_id",
    "contract_id",
    "amendment_type",
    "validity_start_date",
    "validity_end_date",
    "amendment_value",
    "amendment_sequence",
    "source_file",
    "source_row_number",
    "load_date",
    "batch_id",
]
COLUNAS_DIM_SUPPLIER = ["supplier_cnpj", "supplier_key", "economic_group_key"]
COLUNAS_DIM_CONTRACT = [
    "contract_id",
    "contract_key",
    "supplier_key",
    "economic_group_key",
    "category_key",
]
COLUNAS_DIM_CALENDAR = ["calendar_date", "calendar_key"]
COLUNAS_LINHAGEM = ["source_file", "source_row_number", "load_date", "batch_id"]


def localizar_arquivo(tabela, identificador_lote, diretorio):
    arquivo = Path(diretorio) / f"{tabela}_{identificador_lote}.parquet"
    if not arquivo.exists():
        raise FileNotFoundError(f"Não foi encontrado {tabela} para o lote {identificador_lote}: {arquivo}.")
    return arquivo


def carregar_fontes(identificador_lote, staging_dir=STAGING_DIR, curated_dir=CURATED_DIR):
    """Carrega as fontes e dimensões necessárias para resolver os fatos do lote."""
    arquivos = {
        "riscos": (
            localizar_arquivo("stg_homologacoes_risco", identificador_lote, staging_dir),
            COLUNAS_RISCO,
        ),
        "aditamentos": (
            localizar_arquivo("stg_aditamentos", identificador_lote, staging_dir),
            COLUNAS_ADITAMENTOS,
        ),
        "fornecedores": (
            localizar_arquivo("dim_supplier", identificador_lote, curated_dir),
            COLUNAS_DIM_SUPPLIER,
        ),
        "contratos": (
            localizar_arquivo("dim_contract", identificador_lote, curated_dir),
            COLUNAS_DIM_CONTRACT,
        ),
        "calendario": (
            localizar_arquivo("dim_calendar", identificador_lote, curated_dir),
            COLUNAS_DIM_CALENDAR,
        ),
    }
    fontes = {}
    for nome, (arquivo, colunas) in arquivos.items():
        try:
            fontes[nome] = pd.read_parquet(arquivo, columns=colunas)
        except Exception as erro:
            raise ValueError(f"Não foi possível carregar as colunas de {nome}: {erro}") from erro
    return fontes


def adicionar_erro(erros, mascara, mensagem):
    erros.loc[mascara] = erros.loc[mascara].map(
        lambda atual: f"{atual}; {mensagem}" if atual else mensagem
    )


def _adicionar_chaves_de_calendario(df, campos_data, calendario):
    resultado = df.copy()
    chaves_calendario = calendario.set_index("calendar_date")["calendar_key"]
    for campo in campos_data:
        coluna_chave = f"{campo.removesuffix('_date')}_calendar_key"
        resultado[coluna_chave] = resultado[campo].map(chaves_calendario).astype("Int64")
    return resultado


def construir_fact_rfi(fontes):
    """Resolve eventos de homologação e risco por fornecedor e calendário."""
    riscos = fontes["riscos"].copy()
    fornecedores = fontes["fornecedores"].rename(
        columns={"supplier_key": "resolved_supplier_key", "economic_group_key": "resolved_economic_group_key"}
    )
    riscos = riscos.merge(
        fornecedores,
        on="supplier_cnpj",
        how="left",
        validate="many_to_one",
    )
    riscos = _adicionar_chaves_de_calendario(
        riscos,
        ["assessment_date", "last_approval_date", "expiration_date"],
        fontes["calendario"],
    )
    erros = pd.Series("", index=riscos.index, dtype="string")
    adicionar_erro(
        erros,
        riscos["risk_assessment_id"].duplicated(keep=False),
        "risk_assessment_id duplicado na fonte curated",
    )
    adicionar_erro(erros, riscos["resolved_supplier_key"].isna(), "supplier_cnpj não encontrado em dim_supplier")
    adicionar_erro(
        erros,
        riscos["assessment_calendar_key"].isna(),
        "assessment_date não encontrado em dim_calendar",
    )
    for campo in ["last_approval_date", "expiration_date"]:
        adicionar_erro(
            erros,
            riscos[campo].notna() & riscos[f"{campo.removesuffix('_date')}_calendar_key"].isna(),
            f"{campo} não encontrado em dim_calendar",
        )
    riscos["curated_validation_errors"] = erros
    resolvidos = riscos.loc[erros.eq("")].copy()
    excecoes = riscos.loc[erros.ne("")].copy()
    resolvidos["rfi_key"] = ("RFI-" + resolvidos["risk_assessment_id"]).astype("string")
    resolvidos = resolvidos.rename(
        columns={
            "resolved_supplier_key": "supplier_key",
            "resolved_economic_group_key": "economic_group_key",
        }
    )
    colunas = [
        "rfi_key",
        "risk_assessment_id",
        "supplier_key",
        "economic_group_key",
        "assessment_calendar_key",
        "last_approval_calendar_key",
        "expiration_calendar_key",
        "homologation_result",
        "homologation_status",
        "financial_risk",
        "labor_risk",
        "credit_rating",
        "final_risk",
        "interest_to_revenue_ratio",
        "revenue_trend",
        "net_margin",
        "labor_cases_index",
        *COLUNAS_LINHAGEM,
    ]
    return resolvidos[colunas], excecoes


def construir_fact_renewal(fontes):
    """Resolve eventos de renovação e aporte pelo contrato curated publicado."""
    aditamentos = fontes["aditamentos"].copy()
    contratos = fontes["contratos"].rename(
        columns={
            "supplier_key": "resolved_supplier_key",
            "economic_group_key": "resolved_economic_group_key",
            "category_key": "resolved_category_key",
        }
    )
    aditamentos = aditamentos.merge(
        contratos,
        on="contract_id",
        how="left",
        validate="many_to_one",
    )
    aditamentos = _adicionar_chaves_de_calendario(
        aditamentos,
        ["validity_start_date", "validity_end_date"],
        fontes["calendario"],
    )
    erros = pd.Series("", index=aditamentos.index, dtype="string")
    adicionar_erro(
        erros,
        aditamentos["amendment_id"].duplicated(keep=False),
        "amendment_id duplicado na fonte curated",
    )
    adicionar_erro(erros, aditamentos["contract_key"].isna(), "contract_id não encontrado em dim_contract")
    for campo in ["validity_start_date", "validity_end_date"]:
        adicionar_erro(
            erros,
            aditamentos[f"{campo.removesuffix('_date')}_calendar_key"].isna(),
            f"{campo} não encontrado em dim_calendar",
        )
    adicionar_erro(erros, aditamentos["amendment_value"].isna(), "amendment_value ausente ou inválido")
    adicionar_erro(
        erros,
        aditamentos["amendment_value"].le(0).fillna(False),
        "amendment_value deve ser positivo",
    )
    aditamentos["curated_validation_errors"] = erros
    resolvidos = aditamentos.loc[erros.eq("")].copy()
    excecoes = aditamentos.loc[erros.ne("")].copy()
    resolvidos["renewal_key"] = ("RNL-" + resolvidos["amendment_id"]).astype("string")
    resolvidos["is_renewal"] = resolvidos["amendment_type"].eq("renovacao")
    resolvidos = resolvidos.rename(
        columns={
            "resolved_supplier_key": "supplier_key",
            "resolved_economic_group_key": "economic_group_key",
            "resolved_category_key": "category_key",
        }
    )
    colunas = [
        "renewal_key",
        "amendment_id",
        "amendment_sequence",
        "amendment_type",
        "is_renewal",
        "contract_key",
        "supplier_key",
        "economic_group_key",
        "category_key",
        "validity_start_calendar_key",
        "validity_end_calendar_key",
        "amendment_value",
        *COLUNAS_LINHAGEM,
    ]
    return resolvidos[colunas], excecoes


def construir_cobertura(origem, fato, excecoes):
    return {
        "source_row_count": len(origem),
        "fact_row_count": len(fato),
        "exception_row_count": len(excecoes),
        "is_reconciled": len(origem) == len(fato) + len(excecoes),
    }


def executar_publicacao(
    identificador_lote,
    staging_dir=STAGING_DIR,
    curated_dir=CURATED_DIR,
    exceptions_dir=EXCEPTIONS_DIR,
):
    """Publica fatos de risco e renovação para o mesmo lote das dimensões de referência."""
    fontes = carregar_fontes(identificador_lote, staging_dir, curated_dir)
    fact_rfi, excecoes_rfi = construir_fact_rfi(fontes)
    fact_renewal, excecoes_renovacao = construir_fact_renewal(fontes)
    cobertura_rfi = construir_cobertura(fontes["riscos"], fact_rfi, excecoes_rfi)
    cobertura_renovacao = construir_cobertura(fontes["aditamentos"], fact_renewal, excecoes_renovacao)
    if not cobertura_rfi["is_reconciled"] or not cobertura_renovacao["is_reconciled"]:
        raise ValueError("A cobertura entre staging, fatos e exceções falhou.")

    curated_dir = Path(curated_dir)
    exceptions_dir = Path(exceptions_dir)
    curated_dir.mkdir(parents=True, exist_ok=True)
    exceptions_dir.mkdir(parents=True, exist_ok=True)
    arquivo_rfi = curated_dir / f"fact_rfi_{identificador_lote}.parquet"
    arquivo_renovacao = curated_dir / f"fact_renewal_{identificador_lote}.parquet"
    arquivo_excecoes_rfi = exceptions_dir / f"fact_rfi_exceptions_{identificador_lote}.parquet"
    arquivo_excecoes_renovacao = exceptions_dir / f"fact_renewal_exceptions_{identificador_lote}.parquet"
    fact_rfi.to_parquet(arquivo_rfi, index=False)
    fact_renewal.to_parquet(arquivo_renovacao, index=False)
    excecoes_rfi.to_parquet(arquivo_excecoes_rfi, index=False)
    excecoes_renovacao.to_parquet(arquivo_excecoes_renovacao, index=False)

    print(f"Eventos de risco publicados: {len(fact_rfi)}")
    print(f"Eventos de aditamento publicados: {len(fact_renewal)}")
    return {
        "arquivo_fact_rfi": arquivo_rfi,
        "arquivo_fact_renewal": arquivo_renovacao,
        "arquivo_excecoes_rfi": arquivo_excecoes_rfi,
        "arquivo_excecoes_renovacao": arquivo_excecoes_renovacao,
        "rfi_publicados": len(fact_rfi),
        "rfi_invalidos": len(excecoes_rfi),
        "renovacoes_publicadas": len(fact_renewal),
        "renovacoes_invalidas": len(excecoes_renovacao),
        "manifesto": {
            "batch_id": identificador_lote,
            "tables": {
                "fact_rfi": {"row_count": len(fact_rfi)},
                "fact_renewal": {"row_count": len(fact_renewal)},
            },
            "rfi_coverage": cobertura_rfi,
            "renewal_coverage": cobertura_renovacao,
        },
    }
