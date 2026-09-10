"""Publica dimensões curated compartilhadas de calendário e categoria."""

import re
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STAGING_DIR = PROJECT_ROOT / "1.data" / "2.staging"
CURATED_DIR = PROJECT_ROOT / "1.data" / "3.curated"

COLUNAS_DE_DATA = {
    "stg_contratos": ["validity_start_date", "validity_end_date", "risk_evaluation_date", "load_date"],
    "stg_aditamentos": ["validity_start_date", "validity_end_date", "load_date"],
    "stg_pagamentos": ["payment_date", "load_date"],
    "stg_homologacoes_risco": [
        "assessment_date",
        "last_approval_date",
        "expiration_date",
        "load_date",
    ],
}
COLUNAS_DE_CATEGORIA = {
    "stg_contratos": "contract_category",
    "stg_pagamentos": "payment_category",
}
NOMES_MESES = {
    1: "janeiro",
    2: "fevereiro",
    3: "marco",
    4: "abril",
    5: "maio",
    6: "junho",
    7: "julho",
    8: "agosto",
    9: "setembro",
    10: "outubro",
    11: "novembro",
    12: "dezembro",
}
NOMES_DIAS_SEMANA = {
    1: "segunda-feira",
    2: "terca-feira",
    3: "quarta-feira",
    4: "quinta-feira",
    5: "sexta-feira",
    6: "sabado",
    7: "domingo",
}
TAXONOMIA_CATEGORIAS = {
    "aquisicao_de_equipamentos": {
        "category_name": "Aquisição de equipamentos",
        "category_macro_group": "capex_focused",
        "category_group": "operacoes_e_suprimentos",
        "category_family": "equipamentos",
    },
    "consultoria": {
        "category_name": "Consultoria",
        "category_macro_group": "opex_focused",
        "category_group": "servicos_profissionais",
        "category_family": "consultoria",
    },
    "licenca_de_software": {
        "category_name": "Licença de software",
        "category_macro_group": "opex_focused",
        "category_group": "tecnologia",
        "category_family": "software_e_licencas",
    },
    "manutencao_e_suporte": {
        "category_name": "Manutenção e suporte",
        "category_macro_group": "opex_focused",
        "category_group": "tecnologia",
        "category_family": "suporte_tecnologico",
    },
    "outsourcing_de_ti": {
        "category_name": "Outsourcing de TI",
        "category_macro_group": "opex_focused",
        "category_group": "tecnologia",
        "category_family": "servicos_de_ti",
    },
    "servicos_de_infraestrutura": {
        "category_name": "Serviços de infraestrutura",
        "category_macro_group": "opex_focused",
        "category_group": "tecnologia",
        "category_family": "infraestrutura_tecnologica",
    },
    "servicos_de_logistica": {
        "category_name": "Serviços de logística",
        "category_macro_group": "opex_focused",
        "category_group": "operacoes_e_suprimentos",
        "category_family": "logistica",
    },
    "treinamento_e_capacitacao": {
        "category_name": "Treinamento e capacitação",
        "category_macro_group": "opex_focused",
        "category_group": "servicos_profissionais",
        "category_family": "treinamento_e_capacitacao",
    },
}


def extrair_identificador_lote(arquivo_origem):
    correspondencia = re.search(r"_(\d{8}_\d{6})\.parquet$", Path(arquivo_origem).name)
    if not correspondencia:
        raise ValueError(
            f"Não foi possível extrair o identificador de lote de {Path(arquivo_origem).name}."
        )
    return correspondencia.group(1)


def localizar_arquivo_staging(tabela, identificador_lote, staging_dir=STAGING_DIR):
    arquivo = Path(staging_dir) / f"{tabela}_{identificador_lote}.parquet"
    if not arquivo.exists():
        raise FileNotFoundError(f"Não foi encontrada {tabela} para o lote {identificador_lote}: {arquivo}.")
    return arquivo


def carregar_fontes(identificador_lote, staging_dir=STAGING_DIR):
    """Carrega as fontes staging necessárias à cobertura temporal e às categorias."""
    fontes = {}
    for tabela, colunas_data in COLUNAS_DE_DATA.items():
        colunas = [*colunas_data]
        if tabela in COLUNAS_DE_CATEGORIA:
            colunas.append(COLUNAS_DE_CATEGORIA[tabela])
        arquivo = localizar_arquivo_staging(tabela, identificador_lote, staging_dir)
        try:
            fontes[tabela] = pd.read_parquet(arquivo, columns=colunas)
        except Exception as erro:
            raise ValueError(f"Não foi possível carregar as colunas de {tabela}: {erro}") from erro
    return fontes


def construir_dim_calendar(fontes):
    """Gera um calendário diário que cobre todas as datas presentes nas fontes do lote."""
    datas = []
    for tabela, colunas in COLUNAS_DE_DATA.items():
        for coluna in colunas:
            datas.append(pd.to_datetime(fontes[tabela][coluna], errors="coerce"))
    datas_presentes = pd.concat(datas, ignore_index=True).dropna()
    if datas_presentes.empty:
        raise ValueError("Não há datas válidas nas fontes staging para construir dim_calendar.")

    intervalo = pd.date_range(datas_presentes.min().normalize(), datas_presentes.max().normalize(), freq="D")
    calendario = pd.DataFrame({"calendar_date": intervalo.date})
    datas_calendario = pd.to_datetime(calendario["calendar_date"])
    dia_semana = datas_calendario.dt.dayofweek + 1
    calendario["calendar_key"] = datas_calendario.dt.strftime("%Y%m%d").astype("int64")
    calendario["calendar_year"] = datas_calendario.dt.year
    calendario["calendar_semester"] = ((datas_calendario.dt.month - 1) // 6 + 1).astype("int64")
    calendario["calendar_quarter"] = datas_calendario.dt.quarter
    calendario["year_quarter"] = (
        datas_calendario.dt.year.astype("string") + "-T" + datas_calendario.dt.quarter.astype("string")
    )
    calendario["calendar_month"] = datas_calendario.dt.month
    calendario["month_name"] = calendario["calendar_month"].map(NOMES_MESES).astype("string")
    calendario["year_month"] = datas_calendario.dt.strftime("%Y-%m").astype("string")
    calendario["calendar_week"] = datas_calendario.dt.isocalendar().week.astype("int64")
    calendario["day_of_month"] = datas_calendario.dt.day
    calendario["day_of_week"] = dia_semana
    calendario["day_name"] = dia_semana.map(NOMES_DIAS_SEMANA).astype("string")
    calendario["is_weekend"] = dia_semana.ge(6)
    calendario["is_month_start"] = datas_calendario.dt.is_month_start
    calendario["is_month_end"] = datas_calendario.dt.is_month_end
    calendario["is_year_start"] = datas_calendario.dt.is_year_start
    calendario["is_year_end"] = datas_calendario.dt.is_year_end
    return calendario[
        [
            "calendar_key",
            "calendar_date",
            "calendar_year",
            "calendar_semester",
            "calendar_quarter",
            "year_quarter",
            "calendar_month",
            "month_name",
            "year_month",
            "calendar_week",
            "day_of_month",
            "day_of_week",
            "day_name",
            "is_weekend",
            "is_month_start",
            "is_month_end",
            "is_year_start",
            "is_year_end",
        ]
    ]


def construir_dim_category(fontes):
    """Publica uma categoria por código técnico, com três níveis de hierarquia."""
    categorias = pd.concat(
        [
            fontes[tabela][coluna].astype("string").str.strip()
            for tabela, coluna in COLUNAS_DE_CATEGORIA.items()
        ],
        ignore_index=True,
    )
    codigos = categorias.dropna().loc[lambda serie: serie.ne("")].drop_duplicates().sort_values()
    dimensao = pd.DataFrame({"category_code": codigos.to_list()})
    dimensao["category_key"] = ("CAT-" + dimensao["category_code"]).astype("string")
    taxonomia = dimensao["category_code"].map(TAXONOMIA_CATEGORIAS)
    dimensao["is_taxonomy_mapped"] = taxonomia.notna()
    for coluna in ["category_name", "category_macro_group", "category_group", "category_family"]:
        dimensao[coluna] = taxonomia.map(
            lambda atributos, coluna_atual=coluna: (
                atributos[coluna_atual] if isinstance(atributos, dict) else pd.NA
            )
        ).astype("string")
    nao_mapeadas = ~dimensao["is_taxonomy_mapped"]
    dimensao.loc[nao_mapeadas, "category_name"] = dimensao.loc[
        nao_mapeadas, "category_code"
    ].str.replace("_", " ").str.capitalize()
    for coluna in ["category_macro_group", "category_group", "category_family"]:
        dimensao.loc[nao_mapeadas, coluna] = "nao_classificada"
    return dimensao[
        [
            "category_key",
            "category_code",
            "category_name",
            "category_macro_group",
            "category_group",
            "category_family",
            "is_taxonomy_mapped",
        ]
    ]


def executar_publicacao(identificador_lote, staging_dir=STAGING_DIR, curated_dir=CURATED_DIR):
    """Publica dimensões compartilhadas de calendário e categoria para um lote."""
    fontes = carregar_fontes(identificador_lote, staging_dir)
    dim_calendar = construir_dim_calendar(fontes)
    dim_category = construir_dim_category(fontes)

    curated_dir = Path(curated_dir)
    curated_dir.mkdir(parents=True, exist_ok=True)
    arquivo_calendario = curated_dir / f"dim_calendar_{identificador_lote}.parquet"
    arquivo_categoria = curated_dir / f"dim_category_{identificador_lote}.parquet"
    dim_calendar.to_parquet(arquivo_calendario, index=False)
    dim_category.to_parquet(arquivo_categoria, index=False)

    print(f"Calendário publicado: {len(dim_calendar)} dias")
    print(f"Categorias publicadas: {len(dim_category)}")
    return {
        "arquivo_dim_calendar": arquivo_calendario,
        "arquivo_dim_category": arquivo_categoria,
        "dias_publicados": len(dim_calendar),
        "categorias_publicadas": len(dim_category),
        "manifesto": {
            "batch_id": identificador_lote,
            "source_files": {
                tabela: f"{tabela}_{identificador_lote}.parquet" for tabela in COLUNAS_DE_DATA
            },
            "tables": {
                "dim_calendar": {
                    "row_count": len(dim_calendar),
                    "start_date": dim_calendar["calendar_date"].min().isoformat(),
                    "end_date": dim_calendar["calendar_date"].max().isoformat(),
                },
                "dim_category": {"row_count": len(dim_category)},
            },
        },
    }


if __name__ == "__main__":
    arquivo = max(STAGING_DIR.glob("stg_contratos_*.parquet"))
    executar_publicacao(extrair_identificador_lote(arquivo))
