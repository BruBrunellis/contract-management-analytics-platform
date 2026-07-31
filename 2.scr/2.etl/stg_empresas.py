"""Padroniza e valida a fonte RAW de empresas para a camada STAGING."""

import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

try:
    import pyarrow  # noqa: F401
except ImportError as erro:
    raise SystemExit(
        "O pacote pyarrow é necessário para criar arquivos Parquet. "
        "Instale as dependências com: .venv\\Scripts\\python.exe -m pip install -r requirements.txt"
    ) from erro


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "1.data" / "1.raw"
STAGING_DIR = PROJECT_ROOT / "1.data" / "2.staging"
EXCEPTIONS_DIR = STAGING_DIR / "exceptions"
TIMEZONE = ZoneInfo("America/Sao_Paulo")

RENOMEAR_COLUNAS = {
    "CNPJ": "cnpj",
    "CNPJ8": "cnpj8",
    "CNPJ_Matriz": "cnpj_matriz",
    "Razao_Social": "razao_social",
    "Hierarquia": "hierarquia",
    "Capital_Social": "capital_social",
    "Porte_Empresa": "porte_empresa",
    "Num_Func_CLT": "num_func_clt",
    "Num_Func_PJ": "num_func_pj",
    "Num_Total_Func": "num_total_func",
    "Processos_Trabalhistas": "processos_trabalhistas",
}
COLUNAS_FINANCEIRAS = [
    "capital_social",
    *[
        f"{indicador}_{ano}"
        for indicador in ("faturamento", "custo", "lucro_bruto", "juros_divida", "lucro_liquido")
        for ano in range(2022, 2027)
    ],
]
COLUNAS_INTEIRAS = ["num_func_clt", "num_func_pj", "num_total_func", "processos_trabalhistas"]
COLUNAS_COMPARAR_MATRIZ = [*COLUNAS_FINANCEIRAS, "num_total_func"]


def normalizar_identificador(valor):
    """Remove formatação de CNPJ e preserva nulos como texto vazio."""
    if pd.isna(valor):
        return ""
    return re.sub(r"\D", "", str(valor))


def localizar_arquivo_empresas():
    """Retorna a versão mais recente da fonte RAW de empresas."""
    arquivos = sorted(RAW_DIR.glob("empresas_*.csv"))
    if not arquivos:
        raise FileNotFoundError("Nenhum arquivo no padrão empresas_YYYYMMDD.csv foi encontrado na camada RAW.")
    return arquivos[-1]


def preparar_dataframe(arquivo_origem, data_carga=None):
    """Lê a origem, padroniza nomes, tipos e colunas de linhagem."""
    df = pd.read_csv(
        arquivo_origem,
        dtype={"CNPJ": "string", "CNPJ8": "string", "CNPJ_Matriz": "string"},
    ).rename(columns=RENOMEAR_COLUNAS)
    df.columns = [coluna.lower() for coluna in df.columns]

    for coluna in ("cnpj", "cnpj8", "cnpj_matriz"):
        df[coluna] = df[coluna].map(normalizar_identificador).astype("string")
    for coluna in ("razao_social", "hierarquia", "porte_empresa"):
        df[coluna] = df[coluna].astype("string").str.strip()
    for coluna in COLUNAS_FINANCEIRAS:
        df[coluna] = pd.to_numeric(df[coluna], errors="coerce")
    for coluna in COLUNAS_INTEIRAS:
        df[coluna] = pd.to_numeric(df[coluna], errors="coerce").astype("Int64")

    df["source_file"] = arquivo_origem.name
    df["load_date"] = pd.Timestamp(data_carga or datetime.now(TIMEZONE).date())
    df["source_row_number"] = pd.Series(range(2, len(df) + 2), dtype="Int64")
    return df


def adicionar_erro(erros, mascara, mensagem):
    """Adiciona uma mensagem de validação às linhas indicadas pela máscara."""
    erros.loc[mascara] = erros.loc[mascara].map(
        lambda atual: f"{atual}; {mensagem}" if atual else mensagem
    )


def validar_empresas(df):
    """Retorna erros técnicos por linha, sem alterar a fonte de origem."""
    erros = pd.Series("", index=df.index, dtype="string")

    adicionar_erro(erros, df["cnpj"].eq(""), "cnpj ausente")
    adicionar_erro(erros, ~df["cnpj"].str.fullmatch(r"\d{14}", na=False), "cnpj deve conter 14 dígitos")
    adicionar_erro(erros, df["cnpj"].duplicated(keep=False) & df["cnpj"].ne(""), "cnpj duplicado")
    adicionar_erro(erros, df["cnpj8"].eq(""), "cnpj8 ausente")
    adicionar_erro(erros, ~df["cnpj8"].str.fullmatch(r"\d{8}", na=False), "cnpj8 deve conter 8 dígitos")
    adicionar_erro(erros, df["cnpj8"].ne(df["cnpj"].str[:8]), "cnpj8 divergente do cnpj")
    adicionar_erro(erros, df["razao_social"].isna() | df["razao_social"].eq(""), "razao_social ausente")
    adicionar_erro(erros, ~df["hierarquia"].isin(["Matriz", "Filial"]), "hierarquia inválida")
    adicionar_erro(erros, ~df["porte_empresa"].isin(["Microempresa", "Pequeno", "Médio", "Grande"]), "porte_empresa inválido")

    for coluna in [*COLUNAS_FINANCEIRAS, *COLUNAS_INTEIRAS]:
        adicionar_erro(erros, df[coluna].isna(), f"{coluna} ausente ou inválido")
        adicionar_erro(erros, df[coluna].lt(0), f"{coluna} não pode ser negativo")
    adicionar_erro(
        erros,
        (df["num_func_clt"] + df["num_func_pj"]).ne(df["num_total_func"]),
        "total de funcionários divergente de clt + pj",
    )

    mascaras_matriz = df["hierarquia"].eq("Matriz")
    mascaras_filial = df["hierarquia"].eq("Filial")
    adicionar_erro(erros, mascaras_matriz & df["cnpj_matriz"].ne(df["cnpj"]), "matriz deve referenciar o próprio cnpj")
    adicionar_erro(erros, mascaras_filial & df["cnpj_matriz"].eq(""), "filial sem cnpj_matriz")

    matrizes = df.loc[mascaras_matriz, ["cnpj", *COLUNAS_COMPARAR_MATRIZ]].copy()
    matrizes = matrizes.rename(columns={"cnpj": "cnpj_matriz", **{coluna: f"matriz_{coluna}" for coluna in COLUNAS_COMPARAR_MATRIZ}})
    matrizes = matrizes.loc[~matrizes["cnpj_matriz"].duplicated(keep=False)]
    filiais = df.loc[mascaras_filial, ["cnpj_matriz", *COLUNAS_COMPARAR_MATRIZ]].merge(
        matrizes,
        on="cnpj_matriz",
        how="left",
    )
    indices_filiais = df.index[mascaras_filial]
    adicionar_erro(erros, mascaras_filial & ~df["cnpj_matriz"].isin(matrizes["cnpj_matriz"]), "cnpj_matriz não encontrado ou não é matriz")
    for coluna in COLUNAS_COMPARAR_MATRIZ:
        maior_que_matriz = filiais[coluna].gt(filiais[f"matriz_{coluna}"]).fillna(False)
        mascara_global = pd.Series(False, index=df.index)
        mascara_global.loc[indices_filiais] = maior_que_matriz.to_numpy()
        adicionar_erro(erros, mascara_global, f"{coluna} maior que o valor da matriz")
    return erros


def executar_staging(
    arquivo_origem=None,
    identificador_lote=None,
    data_carga=None,
    staging_dir=STAGING_DIR,
    exceptions_dir=EXCEPTIONS_DIR,
):
    """Executa a transformação RAW → STAGING de empresas."""
    arquivo_origem = arquivo_origem or localizar_arquivo_empresas()
    df = preparar_dataframe(arquivo_origem, data_carga)
    df["validation_errors"] = validar_empresas(df)

    staging_dir.mkdir(parents=True, exist_ok=True)
    exceptions_dir.mkdir(parents=True, exist_ok=True)
    validas = df.loc[df["validation_errors"].eq("")].drop(columns="validation_errors")
    invalidas = df.loc[df["validation_errors"].ne("")]

    sufixo = f"_{identificador_lote}" if identificador_lote else ""
    arquivo_staging = staging_dir / f"stg_empresas{sufixo}.parquet"
    arquivo_excecoes = exceptions_dir / f"stg_empresas_invalidas{sufixo}.parquet"
    validas.to_parquet(arquivo_staging, index=False, engine="pyarrow")
    invalidas.to_parquet(arquivo_excecoes, index=False, engine="pyarrow")

    print(f"Fonte RAW: {arquivo_origem.name}")
    print(f"Registros válidos: {len(validas)}")
    print(f"Registros com exceção: {len(invalidas)}")
    print(f"STAGING: {arquivo_staging}")
    print(f"Exceções: {arquivo_excecoes}")
    return {
        "arquivo_staging": arquivo_staging,
        "arquivo_excecoes": arquivo_excecoes,
        "registros_validos": len(validas),
        "registros_invalidos": len(invalidas),
    }


if __name__ == "__main__":
    executar_staging()
