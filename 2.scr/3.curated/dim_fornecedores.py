"""Publica dimensões curated de fornecedores e grupos econômicos."""

import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STAGING_DIR = PROJECT_ROOT / "1.data" / "2.staging"
CURATED_DIR = PROJECT_ROOT / "1.data" / "3.curated"
EXCEPTIONS_DIR = CURATED_DIR / "exceptions"
TIMEZONE = ZoneInfo("America/Sao_Paulo")

COLUNAS_OBRIGATORIAS = [
    "cnpj",
    "cnpj8",
    "cnpj_matriz",
    "razao_social",
    "hierarquia",
    "porte_empresa",
    "atividade_economica",
    "ano_fundacao",
    "idade_empresa",
    "estagio_empresa",
    "cenario_financeiro",
    "source_file",
    "source_row_number",
    "load_date",
    "batch_id",
]
COLUNAS_DESCRITIVAS = [
    "razao_social",
    "hierarquia",
    "porte_empresa",
    "atividade_economica",
    "ano_fundacao",
    "idade_empresa",
    "estagio_empresa",
    "cenario_financeiro",
]
COLUNAS_DESCRITIVAS_TEXTO = [
    "razao_social",
    "hierarquia",
    "porte_empresa",
    "atividade_economica",
    "estagio_empresa",
    "cenario_financeiro",
]
COLUNAS_LINHAGEM = ["source_file", "source_row_number", "load_date", "batch_id"]


def extrair_identificador_lote(arquivo_origem):
    correspondencia = re.search(r"_(\d{8}_\d{6})\.parquet$", Path(arquivo_origem).name)
    if not correspondencia:
        raise ValueError(
            f"Não foi possível extrair o identificador de lote de {Path(arquivo_origem).name}."
        )
    return correspondencia.group(1)


def validar_colunas_obrigatorias(colunas):
    ausentes = sorted(set(COLUNAS_OBRIGATORIAS).difference(colunas))
    if ausentes:
        raise ValueError(
            "stg_empresas sem colunas obrigatórias para publicação curated: "
            f"{', '.join(ausentes)}."
        )


def localizar_arquivo_stg_empresas(identificador_lote, staging_dir=STAGING_DIR):
    arquivo = Path(staging_dir) / f"stg_empresas_{identificador_lote}.parquet"
    if not arquivo.exists():
        raise FileNotFoundError(
            f"Não foi encontrada a staging de empresas do lote {identificador_lote}: {arquivo}."
        )
    return arquivo


def adicionar_erro(erros, mascara, mensagem):
    erros.loc[mascara] = erros.loc[mascara].map(
        lambda atual: f"{atual}; {mensagem}" if atual else mensagem
    )


def contar_erros(erros):
    contador = Counter()
    for erro in erros.dropna():
        contador.update(mensagem.strip() for mensagem in str(erro).split(";") if mensagem.strip())
    return dict(sorted(contador.items()))


def preparar_dataframe(arquivo_stg_empresas):
    """Carrega a staging de empresas e preserva os atributos necessários à dimensão."""
    df = pd.read_parquet(arquivo_stg_empresas).copy()
    validar_colunas_obrigatorias(df.columns)
    for coluna in ("cnpj", "cnpj8", "cnpj_matriz"):
        df[coluna] = df[coluna].astype("string").str.strip()
    for coluna in COLUNAS_DESCRITIVAS_TEXTO:
        df[coluna] = df[coluna].astype("string").str.strip()
    return df


def validar_resolucao(df):
    """Retorna problemas que impedem resolver fornecedor, matriz e grupo econômico."""
    erros = pd.Series("", index=df.index, dtype="string")
    adicionar_erro(erros, ~df["cnpj"].str.fullmatch(r"\d{14}", na=False), "cnpj inválido")
    adicionar_erro(erros, ~df["cnpj8"].str.fullmatch(r"\d{8}", na=False), "cnpj8 inválido")
    adicionar_erro(erros, df["cnpj8"].ne(df["cnpj"].str[:8]), "cnpj8 divergente do cnpj")
    adicionar_erro(erros, df["cnpj"].duplicated(keep=False), "cnpj duplicado na fonte curated")
    adicionar_erro(erros, df["razao_social"].eq(""), "razao_social ausente")
    adicionar_erro(erros, ~df["hierarquia"].isin(["Matriz", "Filial"]), "hierarquia inválida")

    matrizes = df.loc[df["hierarquia"].eq("Matriz")]
    adicionar_erro(
        erros,
        df["hierarquia"].eq("Matriz") & df["cnpj_matriz"].ne(df["cnpj"]),
        "matriz deve referenciar o próprio cnpj",
    )
    adicionar_erro(
        erros,
        df["hierarquia"].eq("Filial") & ~df["cnpj_matriz"].isin(matrizes["cnpj"]),
        "cnpj_matriz não encontrado como matriz",
    )

    quantidade_matrizes = matrizes.groupby("cnpj8")["cnpj"].size()
    grupos_invalidos = df["cnpj8"].map(quantidade_matrizes).ne(1).fillna(True)
    adicionar_erro(
        erros,
        df["cnpj8"].str.fullmatch(r"\d{8}", na=False) & grupos_invalidos,
        "grupo econômico sem matriz única",
    )
    return erros


def construir_dimensoes(df):
    """Deriva dimensões com chaves substitutas estáveis a partir de registros resolvidos."""
    fornecedores = df.copy()
    fornecedores["supplier_key"] = ("SUP-" + fornecedores["cnpj"]).astype("string")
    fornecedores["economic_group_key"] = ("GRP-" + fornecedores["cnpj8"]).astype("string")
    fornecedores["parent_supplier_key"] = pd.Series(pd.NA, index=fornecedores.index, dtype="string")
    mascara_filial = fornecedores["hierarquia"].eq("Filial")
    fornecedores.loc[mascara_filial, "parent_supplier_key"] = (
        "SUP-" + fornecedores.loc[mascara_filial, "cnpj_matriz"]
    )
    fornecedores = fornecedores.rename(
        columns={
            "cnpj": "supplier_cnpj",
            "cnpj8": "supplier_cnpj8",
            "cnpj_matriz": "parent_supplier_cnpj",
            "razao_social": "supplier_legal_name",
            "hierarquia": "supplier_hierarchy",
            "porte_empresa": "company_size",
            "atividade_economica": "economic_activity",
            "ano_fundacao": "foundation_year",
            "idade_empresa": "company_age_years",
            "estagio_empresa": "company_stage",
            "cenario_financeiro": "financial_scenario",
        }
    )
    colunas_fornecedor = [
        "supplier_key",
        "supplier_cnpj",
        "supplier_cnpj8",
        "economic_group_key",
        "parent_supplier_key",
        "parent_supplier_cnpj",
        "supplier_legal_name",
        "supplier_hierarchy",
        "company_size",
        "economic_activity",
        "foundation_year",
        "company_age_years",
        "company_stage",
        "financial_scenario",
        *COLUNAS_LINHAGEM,
    ]

    grupos = fornecedores.loc[fornecedores["supplier_hierarchy"].eq("Matriz")].copy()
    grupos = grupos.rename(
        columns={
            "supplier_cnpj8": "economic_group_cnpj8",
            "supplier_key": "matrix_supplier_key",
            "supplier_legal_name": "economic_group_legal_name",
        }
    )
    colunas_grupo = [
        "economic_group_key",
        "economic_group_cnpj8",
        "matrix_supplier_key",
        "economic_group_legal_name",
        *COLUNAS_LINHAGEM,
    ]
    return fornecedores[colunas_fornecedor], grupos[colunas_grupo]


def executar_publicacao(
    arquivo_stg_empresas=None,
    identificador_lote=None,
    curated_dir=CURATED_DIR,
    exceptions_dir=EXCEPTIONS_DIR,
):
    """Publica `dim_supplier` e `dim_economic_group` para um lote de staging."""
    if arquivo_stg_empresas is None:
        if identificador_lote is None:
            raise ValueError("Informe arquivo_stg_empresas ou identificador_lote.")
        arquivo_stg_empresas = localizar_arquivo_stg_empresas(identificador_lote)
    arquivo_stg_empresas = Path(arquivo_stg_empresas)
    lote = identificador_lote or extrair_identificador_lote(arquivo_stg_empresas)
    df = preparar_dataframe(arquivo_stg_empresas)
    erros = validar_resolucao(df)
    df["curated_validation_errors"] = erros
    resolvidos = df.loc[df["curated_validation_errors"].eq("")].drop(
        columns="curated_validation_errors"
    )
    excecoes = df.loc[df["curated_validation_errors"].ne("")]
    dim_supplier, dim_economic_group = construir_dimensoes(resolvidos)

    curated_dir = Path(curated_dir)
    exceptions_dir = Path(exceptions_dir)
    arquivo_fornecedores = curated_dir / f"dim_supplier_{lote}.parquet"
    arquivo_grupos = curated_dir / f"dim_economic_group_{lote}.parquet"
    arquivo_excecoes = exceptions_dir / f"dim_supplier_resolution_exceptions_{lote}.parquet"
    curated_dir.mkdir(parents=True, exist_ok=True)
    exceptions_dir.mkdir(parents=True, exist_ok=True)
    dim_supplier.to_parquet(arquivo_fornecedores, index=False)
    dim_economic_group.to_parquet(arquivo_grupos, index=False)
    excecoes.to_parquet(arquivo_excecoes, index=False)

    print(f"Fonte STAGING: {arquivo_stg_empresas.name}")
    print(f"Fornecedores publicados: {len(dim_supplier)}")
    print(f"Grupos econômicos publicados: {len(dim_economic_group)}")
    print(f"Registros com exceção: {len(excecoes)}")
    return {
        "arquivo_dim_supplier": arquivo_fornecedores,
        "arquivo_dim_economic_group": arquivo_grupos,
        "arquivo_excecoes": arquivo_excecoes,
        "registros_origem": len(df),
        "fornecedores_publicados": len(dim_supplier),
        "grupos_publicados": len(dim_economic_group),
        "registros_invalidos": len(excecoes),
        "manifesto": {
            "source_file": arquivo_stg_empresas.name,
            "batch_id": lote,
            "published_at": datetime.now(TIMEZONE).isoformat(),
            "tables": {
                "dim_supplier": {"row_count": len(dim_supplier)},
                "dim_economic_group": {"row_count": len(dim_economic_group)},
            },
            "resolution_error_counts": contar_erros(erros),
        },
    }


if __name__ == "__main__":
    executar_publicacao(identificador_lote=extrair_identificador_lote(max(STAGING_DIR.glob("stg_empresas_*.parquet"))))
