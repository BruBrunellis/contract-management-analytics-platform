"""Padroniza e valida a fonte RAW de homologações e risco para STAGING."""

import re
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
    "Id_Avaliacao_Risco": "risk_assessment_id",
    "CNPJ": "supplier_cnpj",
    "Data_Avaliacao": "assessment_date",
    "Data_Ultima_Homologacao": "last_approval_date",
    "Data_Expiracao": "expiration_date",
    "Resultado_Homologacao": "homologation_result",
    "Status_Homologacao": "homologation_status",
    "Risco_Financeiro": "financial_risk",
    "Risco_Trabalhista": "labor_risk",
    "Rating_Credito": "credit_rating",
    "Risco_Final": "final_risk",
    "Indice_Juros_Sobre_Receita": "interest_to_revenue_ratio",
    "Tendencia_Faturamento": "revenue_trend",
    "Margem_Liquida": "net_margin",
    "Indice_Processos_Trabalhistas": "labor_cases_index",
}
COLUNAS_OBRIGATORIAS = list(RENOMEAR_COLUNAS)
COLUNAS_SCORE = [
    "interest_to_revenue_ratio",
    "revenue_trend",
    "net_margin",
    "labor_cases_index",
]
RESULTADOS_VALIDOS = {"aprovada", "reprovada"}
STATUS_VALIDOS = {"ativa", "expirada", "negada"}
RISCOS_VALIDOS = {"baixo", "medio", "alto"}
RATINGS_VALIDOS = {"AAA", "AA", "A", "BBB", "BB", "B", "CCC", "CC", "D"}
ORDEM_RISCO = {"baixo": 1, "medio": 2, "alto": 3}


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


def localizar_arquivo_homologacoes_risco():
    """Retorna a versão mais recente da fonte RAW de homologações e risco."""
    return localizar_arquivo_versionado(RAW_DIR, "homologacoes_risco_*.csv", "homologações e risco")


def preparar_dataframe(arquivo_origem, data_carga=None, identificador_lote=None):
    """Lê a fonte, normaliza tipos e acrescenta metadados de linhagem."""
    bruto = pd.read_csv(
        arquivo_origem,
        dtype={"Id_Avaliacao_Risco": "string", "CNPJ": "string"},
    )
    validar_colunas_obrigatorias(bruto.columns, COLUNAS_OBRIGATORIAS, "homologações e risco")
    df = bruto.rename(columns=RENOMEAR_COLUNAS).copy()
    df["risk_assessment_id"] = df["risk_assessment_id"].map(normalizar_codigo).astype("string")
    df["supplier_cnpj"] = df["supplier_cnpj"].map(normalizar_identificador).astype("string")
    df["supplier_cnpj8"] = df["supplier_cnpj"].str[:8].astype("string")
    for coluna in ["homologation_result", "homologation_status", "financial_risk", "labor_risk", "final_risk"]:
        df[coluna] = df[coluna].map(normalizar_enum).astype("string")
    df["credit_rating"] = df["credit_rating"].astype("string").str.strip().str.upper()
    for coluna in ["assessment_date", "last_approval_date", "expiration_date"]:
        df[coluna] = pd.to_datetime(df[coluna], errors="coerce").dt.date
    for coluna in COLUNAS_SCORE:
        df[coluna] = pd.to_numeric(df[coluna], errors="coerce").astype("Float64")
    return adicionar_linhagem(df, arquivo_origem, data_carga, identificador_lote)


def risco_mais_alto(risco_financeiro, risco_trabalhista):
    if risco_financeiro not in ORDEM_RISCO or risco_trabalhista not in ORDEM_RISCO:
        return None
    return max((risco_financeiro, risco_trabalhista), key=ORDEM_RISCO.get)


def validar_homologacoes_risco(df, data_referencia=None):
    """Retorna erros técnicos por evento de homologação e risco."""
    erros = pd.Series("", index=df.index, dtype="string")
    data_referencia = pd.Timestamp(data_referencia or df["load_date"].iloc[0]).date()
    assessment_dates = pd.to_datetime(df["assessment_date"], errors="coerce")
    approval_dates = pd.to_datetime(df["last_approval_date"], errors="coerce")
    expiration_dates = pd.to_datetime(df["expiration_date"], errors="coerce")

    adicionar_erro(erros, df["risk_assessment_id"].eq(""), "risk_assessment_id ausente")
    adicionar_erro(
        erros,
        ~df["risk_assessment_id"].str.fullmatch(r"RSK\d{9}", na=False),
        "risk_assessment_id deve seguir o padrão RSK#########",
    )
    adicionar_erro(
        erros,
        df["risk_assessment_id"].duplicated(keep=False) & df["risk_assessment_id"].ne(""),
        "risk_assessment_id duplicado",
    )
    adicionar_erro(erros, df["supplier_cnpj"].eq(""), "supplier_cnpj ausente")
    adicionar_erro(
        erros,
        ~df["supplier_cnpj"].str.fullmatch(r"\d{14}", na=False),
        "supplier_cnpj deve conter 14 dígitos",
    )
    adicionar_erro(erros, ~df["supplier_cnpj8"].str.fullmatch(r"\d{8}", na=False), "supplier_cnpj8 inválido")
    adicionar_erro(erros, df["assessment_date"].isna(), "assessment_date ausente ou inválida")

    adicionar_erro(erros, ~df["homologation_result"].isin(RESULTADOS_VALIDOS), "homologation_result inválido")
    adicionar_erro(erros, ~df["homologation_status"].isin(STATUS_VALIDOS), "homologation_status inválido")
    for coluna in ["financial_risk", "labor_risk", "final_risk"]:
        adicionar_erro(erros, ~df[coluna].isin(RISCOS_VALIDOS), f"{coluna} inválido")
    adicionar_erro(erros, ~df["credit_rating"].isin(RATINGS_VALIDOS), "credit_rating inválido")
    for coluna in COLUNAS_SCORE:
        adicionar_erro(erros, df[coluna].isna(), f"{coluna} ausente ou inválido")
    for coluna in ["interest_to_revenue_ratio", "labor_cases_index"]:
        adicionar_erro(erros, df[coluna].lt(0).fillna(False), f"{coluna} não pode ser negativo")

    risco_esperado = df.apply(
        lambda linha: risco_mais_alto(linha["financial_risk"], linha["labor_risk"]),
        axis=1,
    )
    adicionar_erro(
        erros,
        risco_esperado.notna() & df["final_risk"].ne(risco_esperado),
        "final_risk divergente dos riscos financeiro e trabalhista",
    )

    aprovadas = df["homologation_result"].eq("aprovada")
    reprovadas = df["homologation_result"].eq("reprovada")
    adicionar_erro(erros, aprovadas & ~df["homologation_status"].isin({"ativa", "expirada"}), "homologação aprovada com status inválido")
    adicionar_erro(erros, aprovadas & df["final_risk"].eq("alto"), "homologação aprovada com risco final alto")
    adicionar_erro(erros, aprovadas & df["last_approval_date"].isna(), "homologação aprovada sem data de aprovação")
    adicionar_erro(erros, aprovadas & df["expiration_date"].isna(), "homologação aprovada sem data de expiração")
    adicionar_erro(erros, reprovadas & df["homologation_status"].ne("negada"), "homologação reprovada com status inválido")
    adicionar_erro(erros, reprovadas & df["final_risk"].ne("alto"), "homologação reprovada sem risco final alto")
    adicionar_erro(erros, reprovadas & df["last_approval_date"].notna(), "homologação reprovada com data de aprovação")
    adicionar_erro(erros, reprovadas & df["expiration_date"].notna(), "homologação reprovada com data de expiração")

    adicionar_erro(
        erros,
        approval_dates.gt(assessment_dates).fillna(False),
        "data de aprovação posterior à avaliação",
    )
    adicionar_erro(
        erros,
        expiration_dates.le(approval_dates).fillna(False),
        "data de expiração anterior ou igual à aprovação",
    )
    adicionar_erro(
        erros,
        df["homologation_status"].eq("ativa")
        & expiration_dates.lt(pd.Timestamp(data_referencia)).fillna(False),
        "homologação ativa expirada na data de referência",
    )
    adicionar_erro(
        erros,
        df["homologation_status"].eq("expirada")
        & expiration_dates.ge(pd.Timestamp(data_referencia)).fillna(False),
        "homologação expirada sem expiração na data de referência",
    )
    return erros


SCHEMA_HOMOLOGACOES_RISCO = pa.schema(
    [
        pa.field("risk_assessment_id", pa.string(), nullable=False),
        pa.field("supplier_cnpj", pa.string(), nullable=False),
        pa.field("supplier_cnpj8", pa.string(), nullable=False),
        pa.field("assessment_date", pa.date32(), nullable=False),
        pa.field("last_approval_date", pa.date32(), nullable=True),
        pa.field("expiration_date", pa.date32(), nullable=True),
        pa.field("homologation_result", pa.string(), nullable=False),
        pa.field("homologation_status", pa.string(), nullable=False),
        pa.field("financial_risk", pa.string(), nullable=False),
        pa.field("labor_risk", pa.string(), nullable=False),
        pa.field("credit_rating", pa.string(), nullable=False),
        pa.field("final_risk", pa.string(), nullable=False),
        *[pa.field(coluna, pa.float64(), nullable=False) for coluna in COLUNAS_SCORE],
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
    """Executa a transformação RAW → STAGING de homologações e risco."""
    arquivo_origem = arquivo_origem or localizar_arquivo_homologacoes_risco()
    df = preparar_dataframe(arquivo_origem, data_carga, identificador_lote)
    erros = validar_homologacoes_risco(df, data_carga)
    df["validation_errors"] = erros

    sufixo = f"_{identificador_lote}" if identificador_lote else ""
    arquivo_staging = Path(staging_dir) / f"stg_homologacoes_risco{sufixo}.parquet"
    arquivo_excecoes = Path(exceptions_dir) / f"stg_homologacoes_risco_invalidas{sufixo}.parquet"
    validas = df.loc[df["validation_errors"].eq("")].drop(columns="validation_errors")
    invalidas = df.loc[df["validation_errors"].ne("")]
    schema = escrever_parquet(validas, arquivo_staging, SCHEMA_HOMOLOGACOES_RISCO)
    escrever_parquet(invalidas, arquivo_excecoes)

    print(f"Fonte RAW: {Path(arquivo_origem).name}")
    print(f"Registros válidos: {len(validas)}")
    print(f"Registros com exceção: {len(invalidas)}")
    return construir_resultado_staging(
        tabela="stg_homologacoes_risco",
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
