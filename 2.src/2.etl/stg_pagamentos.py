"""Padroniza e valida a fonte RAW de pagamentos para a camada STAGING."""

import re
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pandas as pd
import pyarrow as pa
from staging_framework import (
    adicionar_erro,
    adicionar_linhagem,
    construir_resultado_staging,
    escrever_parquet,
    extrair_identificador_lote,
    localizar_arquivo_versionado,
    validar_colunas_obrigatorias,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "1.data" / "1.raw"
STAGING_DIR = PROJECT_ROOT / "1.data" / "2.staging"
EXCEPTIONS_DIR = STAGING_DIR / "exceptions"

RENOMEAR_COLUNAS = {
    "Cód_Pagamento": "payment_id",
    "Cód_Contrato": "contract_id",
    "CNPJ": "supplier_cnpj",
    "Fornecedor": "supplier_name",
    "Data_Pagamento": "payment_date",
    "Valor_Pago": "payment_value",
    "Centro_Custo": "cost_center",
    "Categoria": "payment_category",
}
COLUNAS_OBRIGATORIAS = list(RENOMEAR_COLUNAS)


def normalizar_identificador(valor):
    if pd.isna(valor):
        return ""
    return re.sub(r"\D", "", str(valor))


def normalizar_codigo(valor):
    if pd.isna(valor):
        return ""
    return str(valor).strip().upper()


def normalizar_enum(valor):
    if pd.isna(valor):
        return ""
    texto = str(valor).strip().lower()
    texto = texto.translate(str.maketrans("áàãâéêíóôõúç", "aaaaeeiooouc"))
    return re.sub(r"[^a-z0-9]+", "_", texto).strip("_")


def localizar_arquivo_pagamentos():
    """Retorna a versão mais recente da fonte RAW de pagamentos."""
    return localizar_arquivo_versionado(RAW_DIR, "spending_ficticio_*.csv", "pagamentos")


def localizar_arquivo_stg_contratos(identificador_lote, staging_dir=STAGING_DIR):
    arquivo = Path(staging_dir) / f"stg_contratos_{identificador_lote}.parquet"
    if not arquivo.exists():
        raise FileNotFoundError(
            f"Não foi encontrada a staging de contratos do lote {identificador_lote}: {arquivo}."
        )
    return arquivo


def carregar_contract_ids(arquivo_stg_contratos):
    """Carrega os contratos válidos usados na validação referencial de pagamentos."""
    contratos = pd.read_parquet(arquivo_stg_contratos, columns=["contract_id"])
    return set(contratos["contract_id"].dropna())


def preparar_dataframe(arquivo_origem, data_carga=None, identificador_lote=None):
    """Lê a fonte e normaliza as chaves, valores, datas e metadados de carga."""
    bruto = pd.read_csv(
        arquivo_origem,
        dtype={"Cód_Pagamento": "string", "Cód_Contrato": "string", "CNPJ": "string"},
    )
    validar_colunas_obrigatorias(bruto.columns, COLUNAS_OBRIGATORIAS, "pagamentos")
    df = bruto.rename(columns=RENOMEAR_COLUNAS).copy()
    df["payment_id"] = df["payment_id"].map(normalizar_codigo).astype("string")
    df["contract_id"] = df["contract_id"].map(normalizar_codigo).astype("string")
    df["supplier_cnpj"] = df["supplier_cnpj"].map(normalizar_identificador).astype("string")
    df["supplier_cnpj8"] = df["supplier_cnpj"].str[:8].astype("string")
    df["supplier_name"] = df["supplier_name"].astype("string").str.strip()
    df["cost_center"] = df["cost_center"].astype("string").str.strip().str.upper()
    df["payment_category"] = df["payment_category"].map(normalizar_enum).astype("string")
    df["payment_date"] = pd.to_datetime(df["payment_date"], errors="coerce").dt.date
    df["payment_value"] = pd.to_numeric(df["payment_value"], errors="coerce").round(2).astype("Float64")
    return adicionar_linhagem(df, arquivo_origem, data_carga, identificador_lote)


def validar_pagamentos(df, contract_ids):
    """Retorna erros de conteúdo por pagamento, incluindo referência ao contrato válido."""
    erros = pd.Series("", index=df.index, dtype="string")
    adicionar_erro(erros, df["payment_id"].eq(""), "payment_id ausente")
    adicionar_erro(
        erros,
        ~df["payment_id"].str.fullmatch(r"PAG\d{8}", na=False),
        "payment_id deve seguir o padrão PAG########",
    )
    adicionar_erro(
        erros,
        df["payment_id"].duplicated(keep=False) & df["payment_id"].ne(""),
        "payment_id duplicado",
    )
    adicionar_erro(erros, df["contract_id"].eq(""), "contract_id ausente")
    adicionar_erro(
        erros,
        ~df["contract_id"].str.fullmatch(r"CS\d{8}", na=False),
        "contract_id deve seguir o padrão CS########",
    )
    adicionar_erro(
        erros,
        df["contract_id"].ne("") & ~df["contract_id"].isin(contract_ids),
        "contract_id não encontrado em stg_contratos",
    )
    adicionar_erro(erros, ~df["supplier_cnpj"].str.fullmatch(r"\d{14}", na=False), "supplier_cnpj inválido")
    adicionar_erro(erros, ~df["supplier_cnpj8"].str.fullmatch(r"\d{8}", na=False), "supplier_cnpj8 inválido")
    adicionar_erro(erros, df["supplier_name"].isna() | df["supplier_name"].eq(""), "supplier_name ausente")
    adicionar_erro(erros, df["payment_date"].isna(), "payment_date ausente ou inválida")
    adicionar_erro(erros, df["payment_value"].isna(), "payment_value ausente ou inválido")
    adicionar_erro(erros, df["payment_value"].le(0).fillna(False), "payment_value deve ser positivo")
    adicionar_erro(erros, ~df["cost_center"].str.fullmatch(r"CC-\d{3}", na=False), "cost_center inválido")
    adicionar_erro(erros, df["payment_category"].isna() | df["payment_category"].eq(""), "payment_category ausente")
    return erros


def _converter_valor_para_decimal(df):
    resultado = df.copy()
    resultado["payment_value"] = pd.Series(
        [
            Decimal(str(valor)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if pd.notna(valor)
            else None
            for valor in resultado["payment_value"]
        ],
        index=resultado.index,
        dtype=object,
    )
    return resultado


SCHEMA_PAGAMENTOS = pa.schema(
    [
        pa.field("payment_id", pa.string(), nullable=False),
        pa.field("contract_id", pa.string(), nullable=False),
        pa.field("supplier_cnpj", pa.string(), nullable=False),
        pa.field("supplier_cnpj8", pa.string(), nullable=False),
        pa.field("supplier_name", pa.string(), nullable=False),
        pa.field("payment_date", pa.date32(), nullable=False),
        pa.field("payment_value", pa.decimal128(18, 2), nullable=False),
        pa.field("cost_center", pa.string(), nullable=False),
        pa.field("payment_category", pa.string(), nullable=False),
        pa.field("source_file", pa.string(), nullable=False),
        pa.field("source_row_number", pa.int64(), nullable=False),
        pa.field("load_date", pa.date32(), nullable=False),
        pa.field("batch_id", pa.string(), nullable=False),
    ]
)


def executar_staging(
    arquivo_origem=None,
    identificador_lote=None,
    data_carga=None,
    staging_dir=STAGING_DIR,
    exceptions_dir=EXCEPTIONS_DIR,
    arquivo_stg_contratos=None,
):
    """Executa a transformação RAW → STAGING de pagamentos."""
    arquivo_origem = arquivo_origem or localizar_arquivo_pagamentos()
    lote = identificador_lote or extrair_identificador_lote(arquivo_origem)
    arquivo_stg_contratos = arquivo_stg_contratos or localizar_arquivo_stg_contratos(lote, staging_dir)
    df = preparar_dataframe(arquivo_origem, data_carga, lote)
    erros = validar_pagamentos(df, carregar_contract_ids(arquivo_stg_contratos))
    df["validation_errors"] = erros

    arquivo_staging = Path(staging_dir) / f"stg_pagamentos_{lote}.parquet"
    arquivo_excecoes = Path(exceptions_dir) / f"stg_pagamentos_invalidos_{lote}.parquet"
    validas = df.loc[df["validation_errors"].eq("")].drop(columns="validation_errors")
    invalidas = df.loc[df["validation_errors"].ne("")]
    schema = escrever_parquet(_converter_valor_para_decimal(validas), arquivo_staging, SCHEMA_PAGAMENTOS)
    escrever_parquet(invalidas, arquivo_excecoes)

    print(f"Fonte RAW: {Path(arquivo_origem).name}")
    print(f"Registros válidos: {len(validas)}")
    print(f"Registros com exceção: {len(invalidas)}")
    return construir_resultado_staging(
        tabela="stg_pagamentos",
        arquivo_origem=arquivo_origem,
        arquivo_staging=arquivo_staging,
        arquivo_excecoes=arquivo_excecoes,
        total_origem=len(df),
        total_validos=len(validas),
        total_invalidos=len(invalidas),
        schema=schema,
        erros=erros,
    )


if __name__ == "__main__":
    executar_staging()
