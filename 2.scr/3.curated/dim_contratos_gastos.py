"""Publica `dim_contract` e `fact_spending` a partir das fontes staging do lote."""

from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STAGING_DIR = PROJECT_ROOT / "1.data" / "2.staging"
CURATED_DIR = PROJECT_ROOT / "1.data" / "3.curated"
EXCEPTIONS_DIR = CURATED_DIR / "exceptions"

COLUNAS_CONTRATOS = [
    "contract_id",
    "contract_name",
    "supplier_cnpj",
    "contract_category",
    "validity_start_date",
    "validity_end_date",
    "original_value",
    "total_value",
    "balance_value",
    "contract_type",
    "contract_status",
    "risk_evaluation_date",
    "final_risk",
    "closure_reason",
    "source_file",
    "source_row_number",
    "load_date",
    "batch_id",
]
COLUNAS_PAGAMENTOS = [
    "payment_id",
    "contract_id",
    "supplier_cnpj",
    "payment_date",
    "payment_value",
    "cost_center",
    "payment_category",
    "source_file",
    "source_row_number",
    "load_date",
    "batch_id",
]
COLUNAS_DIM_SUPPLIER = ["supplier_cnpj", "supplier_key", "economic_group_key"]
COLUNAS_DIM_CATEGORY = ["category_code", "category_key"]
COLUNAS_DIM_CALENDAR = ["calendar_date", "calendar_key"]
COLUNAS_LINHAGEM = ["source_file", "source_row_number", "load_date", "batch_id"]


def localizar_arquivo(tabela, identificador_lote, diretorio):
    arquivo = Path(diretorio) / f"{tabela}_{identificador_lote}.parquet"
    if not arquivo.exists():
        raise FileNotFoundError(f"Não foi encontrado {tabela} para o lote {identificador_lote}: {arquivo}.")
    return arquivo


def carregar_fontes(identificador_lote, staging_dir=STAGING_DIR, curated_dir=CURATED_DIR):
    """Carrega fontes normalizadas e dimensões necessárias para resolver as chaves."""
    arquivos = {
        "contratos": (localizar_arquivo("stg_contratos", identificador_lote, staging_dir), COLUNAS_CONTRATOS),
        "pagamentos": (localizar_arquivo("stg_pagamentos", identificador_lote, staging_dir), COLUNAS_PAGAMENTOS),
        "fornecedores": (localizar_arquivo("dim_supplier", identificador_lote, curated_dir), COLUNAS_DIM_SUPPLIER),
        "categorias": (localizar_arquivo("dim_category", identificador_lote, curated_dir), COLUNAS_DIM_CATEGORY),
        "calendario": (localizar_arquivo("dim_calendar", identificador_lote, curated_dir), COLUNAS_DIM_CALENDAR),
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


def construir_dim_contract(fontes):
    """Resolve contratos contra fornecedor, grupo, categoria e calendário."""
    contratos = fontes["contratos"].copy()
    fornecedores = fontes["fornecedores"].rename(
        columns={"supplier_key": "resolved_supplier_key", "economic_group_key": "resolved_economic_group_key"}
    )
    categorias = fontes["categorias"].rename(columns={"category_key": "resolved_category_key"})
    contratos = contratos.merge(
        fornecedores,
        on="supplier_cnpj",
        how="left",
        validate="many_to_one",
    ).merge(
        categorias,
        left_on="contract_category",
        right_on="category_code",
        how="left",
        validate="many_to_one",
    )
    contratos = _adicionar_chaves_de_calendario(
        contratos,
        ["validity_start_date", "validity_end_date", "risk_evaluation_date"],
        fontes["calendario"],
    )
    erros = pd.Series("", index=contratos.index, dtype="string")
    adicionar_erro(
        erros,
        contratos["contract_id"].duplicated(keep=False),
        "contract_id duplicado na fonte curated",
    )
    adicionar_erro(erros, contratos["resolved_supplier_key"].isna(), "supplier_cnpj não encontrado em dim_supplier")
    adicionar_erro(erros, contratos["resolved_category_key"].isna(), "contract_category não encontrado em dim_category")
    for campo in ["validity_start_date", "validity_end_date"]:
        adicionar_erro(
            erros,
            contratos[f"{campo.removesuffix('_date')}_calendar_key"].isna(),
            f"{campo} não encontrado em dim_calendar",
        )
    adicionar_erro(
        erros,
        contratos["risk_evaluation_date"].notna()
        & contratos["risk_evaluation_calendar_key"].isna(),
        "risk_evaluation_date não encontrado em dim_calendar",
    )
    contratos["curated_validation_errors"] = erros
    resolvidos = contratos.loc[erros.eq("")].copy()
    excecoes = contratos.loc[erros.ne("")].copy()
    resolvidos["contract_key"] = ("CON-" + resolvidos["contract_id"]).astype("string")
    resolvidos = resolvidos.rename(
        columns={
            "resolved_supplier_key": "supplier_key",
            "resolved_economic_group_key": "economic_group_key",
            "resolved_category_key": "category_key",
        }
    )
    colunas = [
        "contract_key",
        "contract_id",
        "supplier_key",
        "economic_group_key",
        "category_key",
        "validity_start_calendar_key",
        "validity_end_calendar_key",
        "risk_evaluation_calendar_key",
        "contract_name",
        "contract_type",
        "contract_status",
        "final_risk",
        "closure_reason",
        "original_value",
        "total_value",
        "balance_value",
        *COLUNAS_LINHAGEM,
    ]
    return resolvidos[colunas], excecoes


def construir_fact_spending(fontes, dim_contract):
    """Resolve pagamentos contra as dimensões e o contrato curated publicado."""
    pagamentos = fontes["pagamentos"].copy()
    contratos = dim_contract[
        ["contract_id", "contract_key", "supplier_key", "economic_group_key", "category_key"]
    ].rename(
        columns={
            "supplier_key": "contract_supplier_key",
            "economic_group_key": "contract_economic_group_key",
            "category_key": "contract_category_key",
        }
    )
    fornecedores = fontes["fornecedores"].rename(
        columns={"supplier_key": "resolved_supplier_key", "economic_group_key": "resolved_economic_group_key"}
    )
    categorias = fontes["categorias"].rename(columns={"category_key": "resolved_category_key"})
    pagamentos = pagamentos.merge(
        contratos,
        on="contract_id",
        how="left",
        validate="many_to_one",
    ).merge(
        fornecedores,
        on="supplier_cnpj",
        how="left",
        validate="many_to_one",
    ).merge(
        categorias,
        left_on="payment_category",
        right_on="category_code",
        how="left",
        validate="many_to_one",
    )
    pagamentos = _adicionar_chaves_de_calendario(pagamentos, ["payment_date"], fontes["calendario"])
    erros = pd.Series("", index=pagamentos.index, dtype="string")
    adicionar_erro(
        erros,
        pagamentos["payment_id"].duplicated(keep=False),
        "payment_id duplicado na fonte curated",
    )
    adicionar_erro(erros, pagamentos["contract_key"].isna(), "contract_id não encontrado em dim_contract")
    adicionar_erro(erros, pagamentos["resolved_supplier_key"].isna(), "supplier_cnpj não encontrado em dim_supplier")
    adicionar_erro(erros, pagamentos["resolved_category_key"].isna(), "payment_category não encontrado em dim_category")
    adicionar_erro(
        erros,
        pagamentos["payment_calendar_key"].isna(),
        "payment_date não encontrado em dim_calendar",
    )
    adicionar_erro(erros, pagamentos["payment_value"].isna(), "payment_value ausente ou inválido")
    adicionar_erro(erros, pagamentos["payment_value"].le(0).fillna(False), "payment_value deve ser positivo")
    adicionar_erro(
        erros,
        pagamentos["contract_key"].notna()
        & pagamentos["resolved_supplier_key"].notna()
        & pagamentos["resolved_supplier_key"].ne(pagamentos["contract_supplier_key"]),
        "supplier_key divergente do contrato",
    )
    adicionar_erro(
        erros,
        pagamentos["contract_key"].notna()
        & pagamentos["resolved_category_key"].notna()
        & pagamentos["resolved_category_key"].ne(pagamentos["contract_category_key"]),
        "category_key divergente do contrato",
    )
    pagamentos["curated_validation_errors"] = erros
    resolvidos = pagamentos.loc[erros.eq("")].copy()
    excecoes = pagamentos.loc[erros.ne("")].copy()
    resolvidos["spending_key"] = ("SPN-" + resolvidos["payment_id"]).astype("string")
    resolvidos = resolvidos.rename(
        columns={
            "resolved_supplier_key": "supplier_key",
            "resolved_economic_group_key": "economic_group_key",
            "resolved_category_key": "category_key",
        }
    )
    colunas = [
        "spending_key",
        "payment_id",
        "contract_key",
        "supplier_key",
        "economic_group_key",
        "category_key",
        "payment_calendar_key",
        "cost_center",
        "payment_value",
        *COLUNAS_LINHAGEM,
    ]
    return resolvidos[colunas], excecoes


def total_monetario(valores):
    total = sum((Decimal(str(valor)) for valor in valores if pd.notna(valor)), Decimal(0))
    return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def construir_reconciliacao(pagamentos, fato, excecoes):
    """Comprova que os pagamentos staging foram todos publicados ou explicados."""
    total_origem = total_monetario(pagamentos["payment_value"])
    total_fato = total_monetario(fato["payment_value"])
    total_excecoes = total_monetario(excecoes["payment_value"])
    return {
        "source_row_count": len(pagamentos),
        "fact_row_count": len(fato),
        "exception_row_count": len(excecoes),
        "source_payment_value": str(total_origem),
        "fact_payment_value": str(total_fato),
        "exception_payment_value": str(total_excecoes),
        "is_row_count_reconciled": len(pagamentos) == len(fato) + len(excecoes),
        "is_payment_value_reconciled": total_origem == total_fato + total_excecoes,
    }


def executar_publicacao(
    identificador_lote,
    staging_dir=STAGING_DIR,
    curated_dir=CURATED_DIR,
    exceptions_dir=EXCEPTIONS_DIR,
):
    """Publica contrato e gastos para o mesmo lote das dimensões de referência."""
    fontes = carregar_fontes(identificador_lote, staging_dir, curated_dir)
    dim_contract, excecoes_contratos = construir_dim_contract(fontes)
    fact_spending, excecoes_pagamentos = construir_fact_spending(fontes, dim_contract)
    reconciliacao = construir_reconciliacao(fontes["pagamentos"], fact_spending, excecoes_pagamentos)
    if not reconciliacao["is_row_count_reconciled"] or not reconciliacao["is_payment_value_reconciled"]:
        raise ValueError("A reconciliação de pagamentos entre staging, fato e exceções falhou.")

    curated_dir = Path(curated_dir)
    exceptions_dir = Path(exceptions_dir)
    curated_dir.mkdir(parents=True, exist_ok=True)
    exceptions_dir.mkdir(parents=True, exist_ok=True)
    arquivo_contratos = curated_dir / f"dim_contract_{identificador_lote}.parquet"
    arquivo_gastos = curated_dir / f"fact_spending_{identificador_lote}.parquet"
    arquivo_excecoes_contratos = exceptions_dir / f"dim_contract_resolution_exceptions_{identificador_lote}.parquet"
    arquivo_excecoes_pagamentos = exceptions_dir / f"fact_spending_exceptions_{identificador_lote}.parquet"
    dim_contract.to_parquet(arquivo_contratos, index=False)
    fact_spending.to_parquet(arquivo_gastos, index=False)
    excecoes_contratos.to_parquet(arquivo_excecoes_contratos, index=False)
    excecoes_pagamentos.to_parquet(arquivo_excecoes_pagamentos, index=False)

    print(f"Contratos publicados: {len(dim_contract)}")
    print(f"Pagamentos publicados: {len(fact_spending)}")
    print(f"Pagamentos com exceção: {len(excecoes_pagamentos)}")
    return {
        "arquivo_dim_contract": arquivo_contratos,
        "arquivo_fact_spending": arquivo_gastos,
        "arquivo_excecoes_contratos": arquivo_excecoes_contratos,
        "arquivo_excecoes_pagamentos": arquivo_excecoes_pagamentos,
        "contratos_publicados": len(dim_contract),
        "contratos_invalidos": len(excecoes_contratos),
        "pagamentos_publicados": len(fact_spending),
        "pagamentos_invalidos": len(excecoes_pagamentos),
        "manifesto": {
            "batch_id": identificador_lote,
            "tables": {
                "dim_contract": {"row_count": len(dim_contract)},
                "fact_spending": {"row_count": len(fact_spending)},
            },
            "contract_resolution_exceptions": len(excecoes_contratos),
            "spending_reconciliation": reconciliacao,
        },
    }
