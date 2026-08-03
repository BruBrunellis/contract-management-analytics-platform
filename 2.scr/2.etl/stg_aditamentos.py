"""Padroniza e valida aditamentos e renovações RAW para a camada STAGING."""

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
    "Cód_Contrato": "contract_id",
    "Tipo_Aditamento": "amendment_type",
    "Vigência_Inicio": "validity_start_date",
    "Vigência_Fim": "validity_end_date",
    "Valor": "amendment_value",
    "Sequencia_Aditamento": "amendment_sequence",
}
COLUNAS_OBRIGATORIAS = list(RENOMEAR_COLUNAS)
TIPOS_VALIDOS = {"renovacao", "aporte"}


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


def construir_amendment_id(contract_id, amendment_sequence):
    """Deriva um ID estável porque a fonte RAW não publica um ID de evento."""
    if not contract_id or pd.isna(amendment_sequence) or amendment_sequence % 1:
        return ""
    return f"AMD-{contract_id}-{int(amendment_sequence):04d}"


def localizar_arquivo_aditamentos():
    """Retorna a versão mais recente da fonte RAW de aditamentos."""
    return localizar_arquivo_versionado(RAW_DIR, "aditamentos_*.csv", "aditamentos")


def localizar_arquivo_stg_contratos(identificador_lote, staging_dir=STAGING_DIR):
    arquivo = Path(staging_dir) / f"stg_contratos_{identificador_lote}.parquet"
    if not arquivo.exists():
        raise FileNotFoundError(
            f"Não foi encontrada a staging de contratos do lote {identificador_lote}: {arquivo}."
        )
    return arquivo


def carregar_contract_ids(arquivo_stg_contratos):
    """Carrega contratos válidos usados na validação referencial de aditamentos."""
    contratos = pd.read_parquet(arquivo_stg_contratos, columns=["contract_id"])
    return set(contratos["contract_id"].dropna())


def preparar_dataframe(arquivo_origem, data_carga=None, identificador_lote=None):
    """Lê a fonte e normaliza chaves, tipos, valores, datas e linhagem."""
    bruto = pd.read_csv(arquivo_origem, dtype={"Cód_Contrato": "string"})
    validar_colunas_obrigatorias(bruto.columns, COLUNAS_OBRIGATORIAS, "aditamentos")
    df = bruto.rename(columns=RENOMEAR_COLUNAS).copy()
    df["contract_id"] = df["contract_id"].map(normalizar_codigo).astype("string")
    df["amendment_type"] = df["amendment_type"].map(normalizar_enum).astype("string")
    df["validity_start_date"] = pd.to_datetime(df["validity_start_date"], errors="coerce").dt.date
    df["validity_end_date"] = pd.to_datetime(df["validity_end_date"], errors="coerce").dt.date
    df["amendment_value"] = pd.to_numeric(df["amendment_value"], errors="coerce").round(2).astype("Float64")
    df["amendment_sequence"] = pd.to_numeric(
        df["amendment_sequence"], errors="coerce"
    ).astype("Float64")
    df["amendment_id"] = pd.Series(
        [
            construir_amendment_id(contract_id, sequence)
            for contract_id, sequence in zip(df["contract_id"], df["amendment_sequence"])
        ],
        index=df.index,
        dtype="string",
    )
    colunas = ["amendment_id", *RENOMEAR_COLUNAS.values()]
    return adicionar_linhagem(df[colunas], arquivo_origem, data_carga, identificador_lote)


def _adicionar_validacao_de_aportes(erros, df):
    datas_validas = (
        df["validity_start_date"].notna()
        & df["validity_end_date"].notna()
        & df["validity_start_date"].le(df["validity_end_date"])
    )
    renovacoes = df.loc[df["amendment_type"].eq("renovacao") & datas_validas]
    for indice, aporte in df.loc[df["amendment_type"].eq("aporte") & datas_validas].iterrows():
        janelas = renovacoes.loc[renovacoes["contract_id"].eq(aporte["contract_id"])]
        pertence_a_renovacao = (
            janelas["validity_start_date"].le(aporte["validity_start_date"])
            & janelas["validity_end_date"].ge(aporte["validity_end_date"])
        ).any()
        if not pertence_a_renovacao:
                adicionar_erro(
                    erros,
                    pd.Series(erros.index == indice, index=erros.index),
                    "aporte fora da vigência de uma renovação",
                )


def validar_aditamentos(df, contract_ids):
    """Retorna erros de conteúdo, referência e coerência temporal por evento."""
    erros = pd.Series("", index=df.index, dtype="string")
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
    adicionar_erro(erros, ~df["amendment_type"].isin(TIPOS_VALIDOS), "amendment_type inválido")
    adicionar_erro(erros, df["validity_start_date"].isna(), "validity_start_date ausente ou inválida")
    adicionar_erro(erros, df["validity_end_date"].isna(), "validity_end_date ausente ou inválida")
    adicionar_erro(
        erros,
        df["validity_start_date"].gt(df["validity_end_date"]).fillna(False),
        "vigência inicial posterior à final",
    )
    adicionar_erro(erros, df["amendment_value"].isna(), "amendment_value ausente ou inválido")
    adicionar_erro(
        erros, df["amendment_value"].le(0).fillna(False), "amendment_value deve ser positivo"
    )
    adicionar_erro(erros, df["amendment_sequence"].isna(), "amendment_sequence ausente ou inválida")
    adicionar_erro(
        erros,
        df["amendment_sequence"].notna() & df["amendment_sequence"].mod(1).ne(0),
        "amendment_sequence deve ser inteira",
    )
    adicionar_erro(
        erros,
        df["amendment_sequence"].le(0).fillna(False),
        "amendment_sequence deve ser positiva",
    )
    chave_evento = df[["contract_id", "amendment_sequence"]].copy()
    evento_duplicado = chave_evento.duplicated(keep=False) & df["contract_id"].ne("") & df[
        "amendment_sequence"
    ].notna()
    adicionar_erro(erros, evento_duplicado, "evento de aditamento duplicado")
    _adicionar_validacao_de_aportes(erros, df)
    return erros


def _converter_para_schema(df):
    resultado = df.copy()
    resultado["amendment_sequence"] = resultado["amendment_sequence"].astype("int64")
    resultado["amendment_value"] = pd.Series(
        [
            Decimal(str(valor)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            for valor in resultado["amendment_value"]
        ],
        index=resultado.index,
        dtype=object,
    )
    return resultado


SCHEMA_ADITAMENTOS = pa.schema(
    [
        pa.field("amendment_id", pa.string(), nullable=False),
        pa.field("contract_id", pa.string(), nullable=False),
        pa.field("amendment_type", pa.string(), nullable=False),
        pa.field("validity_start_date", pa.date32(), nullable=False),
        pa.field("validity_end_date", pa.date32(), nullable=False),
        pa.field("amendment_value", pa.decimal128(18, 2), nullable=False),
        pa.field("amendment_sequence", pa.int64(), nullable=False),
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
    """Executa a transformação RAW → STAGING de aditamentos e renovações."""
    arquivo_origem = arquivo_origem or localizar_arquivo_aditamentos()
    lote = identificador_lote or extrair_identificador_lote(arquivo_origem)
    arquivo_stg_contratos = arquivo_stg_contratos or localizar_arquivo_stg_contratos(lote, staging_dir)
    df = preparar_dataframe(arquivo_origem, data_carga, lote)
    erros = validar_aditamentos(df, carregar_contract_ids(arquivo_stg_contratos))
    df["validation_errors"] = erros

    arquivo_staging = Path(staging_dir) / f"stg_aditamentos_{lote}.parquet"
    arquivo_excecoes = Path(exceptions_dir) / f"stg_aditamentos_invalidos_{lote}.parquet"
    validas = df.loc[df["validation_errors"].eq("")].drop(columns="validation_errors")
    invalidas = df.loc[df["validation_errors"].ne("")]
    schema = escrever_parquet(_converter_para_schema(validas), arquivo_staging, SCHEMA_ADITAMENTOS)
    escrever_parquet(invalidas, arquivo_excecoes)

    print(f"Fonte RAW: {Path(arquivo_origem).name}")
    print(f"Registros válidos: {len(validas)}")
    print(f"Registros com exceção: {len(invalidas)}")
    return construir_resultado_staging(
        tabela="stg_aditamentos",
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
