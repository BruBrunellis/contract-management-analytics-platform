"""Padroniza e valida a fonte RAW de contratos para a camada STAGING."""

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
    localizar_arquivo_versionado,
    validar_colunas_obrigatorias,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "1.data" / "1.raw"
STAGING_DIR = PROJECT_ROOT / "1.data" / "2.staging"
EXCEPTIONS_DIR = STAGING_DIR / "exceptions"

RENOMEAR_COLUNAS = {
    "Cód_Contrato": "contract_id",
    "Nome_Contrato": "contract_name",
    "CNPJ": "supplier_cnpj",
    "Fornecedor": "supplier_name",
    "Escopo": "contract_category",
    "Vigência Inicio": "validity_start_date",
    "Vigência Fim": "validity_end_date",
    "Valor_Original": "original_value",
    "Valor_Total": "total_value",
    "Saldo": "balance_value",
    "Tipo_Contrato": "contract_type",
    "Status": "contract_status",
    "Data_Avaliacao_Risco": "risk_evaluation_date",
    "Risco_Final": "final_risk",
    "Motivo_Encerramento": "closure_reason",
}
COLUNAS_OBRIGATORIAS = list(RENOMEAR_COLUNAS)
COLUNAS_TEXTO = ["contract_id", "contract_name", "supplier_cnpj", "supplier_name"]
COLUNAS_MONETARIAS = ["original_value", "total_value", "balance_value"]
STATUS_VALIDOS = {"ativo", "vencido", "encerrado"}
TIPOS_VALIDOS = {"novo_contrato", "contrato_renovado"}


def normalizar_identificador(valor):
    """Remove formatação de CNPJ e preserva nulos como texto vazio."""
    if pd.isna(valor):
        return ""
    return re.sub(r"\D", "", str(valor))


def normalizar_codigo(valor):
    if pd.isna(valor):
        return ""
    return str(valor).strip().upper()


def normalizar_enum(valor):
    """Converte rótulos da fonte em valores técnicos estáveis, sem acentos."""
    if pd.isna(valor):
        return ""
    texto = str(valor).strip().lower()
    texto = texto.translate(str.maketrans("áàãâéêíóôõúç", "aaaaeeiooouc"))
    return re.sub(r"[^a-z0-9]+", "_", texto).strip("_")


def localizar_arquivo_contratos():
    """Retorna a versão mais recente da fonte RAW de contratos."""
    return localizar_arquivo_versionado(RAW_DIR, "contratos_ficticios_*.csv", "contratos")


def preparar_dataframe(arquivo_origem, data_carga=None, identificador_lote=None):
    """Lê a fonte, normaliza nomes, tipos e metadados de linhagem."""
    bruto = pd.read_csv(arquivo_origem, dtype={"Cód_Contrato": "string", "CNPJ": "string"})
    validar_colunas_obrigatorias(bruto.columns, COLUNAS_OBRIGATORIAS, "contratos")
    df = bruto.rename(columns=RENOMEAR_COLUNAS).copy()

    df["contract_id"] = df["contract_id"].map(normalizar_codigo).astype("string")
    df["supplier_cnpj"] = df["supplier_cnpj"].map(normalizar_identificador).astype("string")
    for coluna in ["contract_name", "supplier_name"]:
        df[coluna] = df[coluna].astype("string").str.strip()
    for coluna in ["contract_category", "contract_type", "contract_status", "final_risk"]:
        df[coluna] = df[coluna].map(normalizar_enum).astype("string")
    df["closure_reason"] = df["closure_reason"].astype("string").str.strip().replace("", pd.NA)
    for coluna in ["validity_start_date", "validity_end_date", "risk_evaluation_date"]:
        df[coluna] = pd.to_datetime(df[coluna], errors="coerce").dt.date
    for coluna in COLUNAS_MONETARIAS:
        df[coluna] = pd.to_numeric(df[coluna], errors="coerce").round(2).astype("Float64")

    return adicionar_linhagem(df, arquivo_origem, data_carga, identificador_lote)


def validar_contratos(df):
    """Retorna os erros técnicos de cada contrato, sem alterar a fonte."""
    erros = pd.Series("", index=df.index, dtype="string")
    adicionar_erro(erros, df["contract_id"].eq(""), "contract_id ausente")
    adicionar_erro(
        erros,
        ~df["contract_id"].str.fullmatch(r"CS\d{8}", na=False),
        "contract_id deve seguir o padrão CS########",
    )
    adicionar_erro(
        erros,
        df["contract_id"].duplicated(keep=False) & df["contract_id"].ne(""),
        "contract_id duplicado",
    )
    adicionar_erro(erros, df["supplier_cnpj"].eq(""), "supplier_cnpj ausente")
    adicionar_erro(
        erros,
        ~df["supplier_cnpj"].str.fullmatch(r"\d{14}", na=False),
        "supplier_cnpj deve conter 14 dígitos",
    )
    for coluna in ["contract_name", "supplier_name", "contract_category", "final_risk"]:
        adicionar_erro(erros, df[coluna].isna() | df[coluna].eq(""), f"{coluna} ausente")
    adicionar_erro(erros, ~df["contract_status"].isin(STATUS_VALIDOS), "contract_status inválido")
    adicionar_erro(erros, ~df["contract_type"].isin(TIPOS_VALIDOS), "contract_type inválido")
    adicionar_erro(erros, df["validity_start_date"].isna(), "validity_start_date ausente ou inválida")
    adicionar_erro(erros, df["validity_end_date"].isna(), "validity_end_date ausente ou inválida")
    adicionar_erro(
        erros,
        df["validity_start_date"].gt(df["validity_end_date"]).fillna(False),
        "vigência inicial posterior à final",
    )
    for coluna in COLUNAS_MONETARIAS:
        adicionar_erro(erros, df[coluna].isna(), f"{coluna} ausente ou inválido")
        adicionar_erro(erros, df[coluna].lt(0).fillna(False), f"{coluna} não pode ser negativo")
    adicionar_erro(
        erros,
        df["total_value"].lt(df["original_value"]).fillna(False),
        "total_value não pode ser menor que original_value",
    )
    adicionar_erro(
        erros,
        df["balance_value"].gt(df["total_value"]).fillna(False),
        "balance_value não pode superar total_value",
    )
    encerrados = df["contract_status"].eq("encerrado")
    adicionar_erro(erros, encerrados & df["risk_evaluation_date"].isna(), "encerrado sem data de avaliação de risco")
    adicionar_erro(erros, encerrados & df["closure_reason"].isna(), "encerrado sem motivo de encerramento")
    adicionar_erro(erros, ~encerrados & df["closure_reason"].notna(), "motivo de encerramento em contrato não encerrado")
    return erros


def _converter_monetarios_para_decimal(df):
    resultado = df.copy()
    fator = Decimal("0.01")
    for coluna in COLUNAS_MONETARIAS:
        resultado[coluna] = pd.Series(
            [
                Decimal(str(valor)).quantize(fator, rounding=ROUND_HALF_UP)
                if pd.notna(valor)
                else None
                for valor in resultado[coluna]
            ],
            index=resultado.index,
            dtype=object,
        )
    return resultado


SCHEMA_CONTRATOS = pa.schema(
    [
        pa.field("contract_id", pa.string(), nullable=False),
        pa.field("contract_name", pa.string(), nullable=False),
        pa.field("supplier_cnpj", pa.string(), nullable=False),
        pa.field("supplier_name", pa.string(), nullable=False),
        pa.field("contract_category", pa.string(), nullable=False),
        pa.field("validity_start_date", pa.date32(), nullable=False),
        pa.field("validity_end_date", pa.date32(), nullable=False),
        *[pa.field(coluna, pa.decimal128(18, 2), nullable=False) for coluna in COLUNAS_MONETARIAS],
        pa.field("contract_type", pa.string(), nullable=False),
        pa.field("contract_status", pa.string(), nullable=False),
        pa.field("risk_evaluation_date", pa.date32(), nullable=True),
        pa.field("final_risk", pa.string(), nullable=False),
        pa.field("closure_reason", pa.string(), nullable=True),
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
):
    """Executa a transformação RAW → STAGING de contratos."""
    arquivo_origem = arquivo_origem or localizar_arquivo_contratos()
    df = preparar_dataframe(arquivo_origem, data_carga, identificador_lote)
    erros = validar_contratos(df)
    df["validation_errors"] = erros

    sufixo = f"_{identificador_lote}" if identificador_lote else ""
    arquivo_staging = Path(staging_dir) / f"stg_contratos{sufixo}.parquet"
    arquivo_excecoes = Path(exceptions_dir) / f"stg_contratos_invalidos{sufixo}.parquet"
    validas = df.loc[df["validation_errors"].eq("")].drop(columns="validation_errors")
    invalidas = df.loc[df["validation_errors"].ne("")]
    schema = escrever_parquet(_converter_monetarios_para_decimal(validas), arquivo_staging, SCHEMA_CONTRATOS)
    escrever_parquet(invalidas, arquivo_excecoes)

    print(f"Fonte RAW: {Path(arquivo_origem).name}")
    print(f"Registros válidos: {len(validas)}")
    print(f"Registros com exceção: {len(invalidas)}")
    return construir_resultado_staging(
        tabela="stg_contratos",
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
