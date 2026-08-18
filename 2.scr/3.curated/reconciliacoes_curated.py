"""Consolida reconciliações e quality gate da camada curated por lote."""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STAGING_DIR = PROJECT_ROOT / "1.data" / "2.staging"
CURATED_DIR = PROJECT_ROOT / "1.data" / "3.curated"
EXCEPTIONS_DIR = CURATED_DIR / "exceptions"

COLUNAS_LINHAGEM = ["source_file", "source_row_number", "load_date"]
MAPEAMENTOS_DIRETOS = [
    {
        "entity": "dim_supplier",
        "source": "stg_empresas",
        "target": "dim_supplier",
        "exceptions": "dim_supplier_resolution_exceptions",
        "business_key": "cnpj",
    },
    {
        "entity": "dim_contract",
        "source": "stg_contratos",
        "target": "dim_contract",
        "exceptions": "dim_contract_resolution_exceptions",
        "business_key": "contract_id",
    },
    {
        "entity": "fact_spending",
        "source": "stg_pagamentos",
        "target": "fact_spending",
        "exceptions": "fact_spending_exceptions",
        "business_key": "payment_id",
        "monetary_column": "payment_value",
    },
    {
        "entity": "fact_rfi",
        "source": "stg_homologacoes_risco",
        "target": "fact_rfi",
        "exceptions": "fact_rfi_exceptions",
        "business_key": "risk_assessment_id",
    },
    {
        "entity": "fact_renewal",
        "source": "stg_aditamentos",
        "target": "fact_renewal",
        "exceptions": "fact_renewal_exceptions",
        "business_key": "amendment_id",
        "monetary_column": "amendment_value",
    },
]
COLUNAS_STAGING = {
    "stg_empresas": ["cnpj"],
    "stg_contratos": [
        "contract_id",
        "contract_category",
        "validity_start_date",
        "validity_end_date",
        "risk_evaluation_date",
    ],
    "stg_pagamentos": ["payment_id", "payment_date", "payment_category", "payment_value"],
    "stg_homologacoes_risco": [
        "risk_assessment_id",
        "assessment_date",
        "last_approval_date",
        "expiration_date",
    ],
    "stg_aditamentos": ["amendment_id", "validity_start_date", "validity_end_date", "amendment_value"],
}
COLUNAS_CURATED = {
    "dim_supplier": ["supplier_cnpj", "economic_group_key"],
    "dim_economic_group": ["economic_group_key"],
    "dim_calendar": ["calendar_date", "calendar_key"],
    "dim_category": ["category_code", "category_key"],
    "dim_contract": ["contract_id"],
    "fact_spending": ["payment_id", "payment_value"],
    "fact_rfi": ["risk_assessment_id"],
    "fact_renewal": ["amendment_id", "amendment_value"],
}


@dataclass(frozen=True)
class QualityThresholds:
    """Limiares que determinam se uma execução curated é aprovada."""

    min_match_rate: float = 0.95
    financial_tolerance: Decimal = Decimal("0.00")


class CuratedQualityError(ValueError):
    """Indica que o lote foi materializado, mas reprovado no quality gate."""


def localizar_arquivo(tabela, identificador_lote, diretorio):
    arquivo = Path(diretorio) / f"{tabela}_{identificador_lote}.parquet"
    if not arquivo.exists():
        raise FileNotFoundError(f"Não foi encontrado {tabela} para o lote {identificador_lote}: {arquivo}.")
    return arquivo


def carregar_fontes(identificador_lote, staging_dir=STAGING_DIR, curated_dir=CURATED_DIR, exceptions_dir=EXCEPTIONS_DIR):
    """Carrega as fontes necessárias para conciliar o lote completo."""
    fontes = {}
    for tabela, colunas in COLUNAS_STAGING.items():
        fontes[tabela] = pd.read_parquet(localizar_arquivo(tabela, identificador_lote, staging_dir), columns=colunas)
    for tabela, colunas in COLUNAS_CURATED.items():
        fontes[tabela] = pd.read_parquet(localizar_arquivo(tabela, identificador_lote, curated_dir), columns=colunas)
    for mapeamento in MAPEAMENTOS_DIRETOS:
        tabela = mapeamento["exceptions"]
        fontes[tabela] = pd.read_parquet(localizar_arquivo(tabela, identificador_lote, exceptions_dir))
    return fontes


def total_monetario(valores):
    total = sum((Decimal(str(valor)) for valor in valores if pd.notna(valor)), Decimal(0))
    return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _taxa_match(publicados, origem):
    return 1.0 if origem == 0 else publicados / origem


def _registro_direto(mapeamento, fontes):
    origem = fontes[mapeamento["source"]]
    destino = fontes[mapeamento["target"]]
    excecoes = fontes[mapeamento["exceptions"]]
    publicado = len(destino)
    invalido = len(excecoes)
    coluna_monetaria = mapeamento.get("monetary_column")
    if coluna_monetaria:
        total_origem = total_monetario(origem[coluna_monetaria])
        total_destino = total_monetario(destino[coluna_monetaria])
        total_excecoes = total_monetario(excecoes[coluna_monetaria])
        diferenca_monetaria = total_origem - total_destino - total_excecoes
    else:
        total_origem = total_destino = total_excecoes = diferenca_monetaria = None
    return {
        "entity": mapeamento["entity"],
        "reconciliation_type": "direct",
        "source_table": mapeamento["source"],
        "curated_table": mapeamento["target"],
        "exception_table": mapeamento["exceptions"],
        "source_row_count": len(origem),
        "published_row_count": publicado,
        "exception_row_count": invalido,
        "match_rate": _taxa_match(publicado, len(origem)),
        "row_count_delta": len(origem) - publicado - invalido,
        "source_monetary_total": str(total_origem) if total_origem is not None else pd.NA,
        "curated_monetary_total": str(total_destino) if total_destino is not None else pd.NA,
        "exception_monetary_total": str(total_excecoes) if total_excecoes is not None else pd.NA,
        "monetary_delta": str(diferenca_monetaria) if diferenca_monetaria is not None else pd.NA,
        "is_row_count_reconciled": len(origem) == publicado + invalido,
        "is_monetary_reconciled": diferenca_monetaria == Decimal(0) if diferenca_monetaria is not None else True,
    }


def _registro_derivado(entity, source_table, curated_table, expected_keys, actual_keys):
    expected = set(expected_keys.dropna())
    actual = set(actual_keys.dropna())
    correspondentes = len(expected.intersection(actual))
    return {
        "entity": entity,
        "reconciliation_type": "derived",
        "source_table": source_table,
        "curated_table": curated_table,
        "exception_table": pd.NA,
        "source_row_count": len(expected),
        "published_row_count": len(actual),
        "exception_row_count": 0,
        "match_rate": _taxa_match(correspondentes, len(expected)),
        "row_count_delta": len(expected) - len(actual),
        "source_monetary_total": pd.NA,
        "curated_monetary_total": pd.NA,
        "exception_monetary_total": pd.NA,
        "monetary_delta": pd.NA,
        "is_row_count_reconciled": expected == actual,
        "is_monetary_reconciled": True,
    }


def construir_reconciliacoes(fontes):
    """Calcula controles diretos e invariantes das dimensões derivadas."""
    registros = [_registro_direto(mapeamento, fontes) for mapeamento in MAPEAMENTOS_DIRETOS]
    registros.append(
        _registro_derivado(
            "dim_economic_group",
            "dim_supplier",
            "dim_economic_group",
            fontes["dim_supplier"]["economic_group_key"],
            fontes["dim_economic_group"]["economic_group_key"],
        )
    )
    categorias_esperadas = pd.concat(
        [fontes["stg_contratos"]["contract_category"], fontes["stg_pagamentos"]["payment_category"]],
        ignore_index=True,
    )
    registros.append(
        _registro_derivado(
            "dim_category",
            "stg_contratos + stg_pagamentos",
            "dim_category",
            categorias_esperadas,
            fontes["dim_category"]["category_code"],
        )
    )
    datas = []
    for tabela, colunas in {
        "stg_contratos": ["validity_start_date", "validity_end_date", "risk_evaluation_date"],
        "stg_pagamentos": ["payment_date"],
        "stg_homologacoes_risco": ["assessment_date", "last_approval_date", "expiration_date"],
        "stg_aditamentos": ["validity_start_date", "validity_end_date"],
    }.items():
        for coluna in colunas:
            datas.append(pd.to_datetime(fontes[tabela][coluna], errors="coerce"))
    datas_presentes = pd.concat(datas, ignore_index=True).dropna()
    intervalo = pd.date_range(datas_presentes.min().normalize(), datas_presentes.max().normalize(), freq="D")
    registros.append(
        _registro_derivado(
            "dim_calendar",
            "stagings do lote",
            "dim_calendar",
            pd.Series(intervalo.date),
            fontes["dim_calendar"]["calendar_date"],
        )
    )
    return pd.DataFrame(registros)


def aplicar_limiares(relatorio, limiares):
    """Marca cada entidade como aprovada ou reprovada sem perder suas evidências."""
    resultado = relatorio.copy()
    status = []
    motivos = []
    for _, linha in resultado.iterrows():
        falhas = []
        if not linha["is_row_count_reconciled"]:
            falhas.append("contagem não reconciliada")
        if float(linha["match_rate"]) < limiares.min_match_rate:
            falhas.append("match rate abaixo do limiar")
        if not linha["is_monetary_reconciled"]:
            diferenca = abs(Decimal(str(linha["monetary_delta"])))
            if diferenca > limiares.financial_tolerance:
                falhas.append("diferença financeira acima da tolerância")
        status.append("failed" if falhas else "approved")
        motivos.append("; ".join(falhas))
    resultado["status"] = pd.Series(status, dtype="string")
    resultado["failure_reasons"] = pd.Series(motivos, dtype="string")
    return resultado


def construir_indice_excecoes(fontes, identificador_lote):
    """Padroniza as exceções curated mantendo chave, causa e linhagem auditáveis."""
    registros = []
    for mapeamento in MAPEAMENTOS_DIRETOS:
        excecoes = fontes[mapeamento["exceptions"]].copy()
        if excecoes.empty:
            continue
        chave = mapeamento["business_key"]
        indice = pd.DataFrame(
            {
                "batch_id": identificador_lote,
                "entity": mapeamento["entity"],
                "exception_file": f"{mapeamento['exceptions']}_{identificador_lote}.parquet",
                "business_key_type": chave,
                "business_key": excecoes[chave].astype("string"),
                "exception_cause": excecoes["curated_validation_errors"].astype("string"),
            }
        )
        for coluna in COLUNAS_LINHAGEM:
            indice[coluna] = excecoes.get(coluna, pd.NA)
        indice["source_batch_id"] = excecoes.get("batch_id", pd.NA)
        registros.append(indice)
    colunas = [
        "batch_id",
        "entity",
        "exception_file",
        "business_key_type",
        "business_key",
        "exception_cause",
        *COLUNAS_LINHAGEM,
        "source_batch_id",
    ]
    return pd.concat(registros, ignore_index=True)[colunas] if registros else pd.DataFrame(columns=colunas)


def executar_reconciliacoes(
    identificador_lote,
    staging_dir=STAGING_DIR,
    curated_dir=CURATED_DIR,
    exceptions_dir=EXCEPTIONS_DIR,
    min_match_rate=0.95,
    financial_tolerance=Decimal("0.00"),
):
    """Publica relatório e índice de exceções e devolve o resultado do quality gate."""
    limiares = QualityThresholds(float(min_match_rate), Decimal(str(financial_tolerance)))
    fontes = carregar_fontes(identificador_lote, staging_dir, curated_dir, exceptions_dir)
    relatorio = aplicar_limiares(construir_reconciliacoes(fontes), limiares)
    indice_excecoes = construir_indice_excecoes(fontes, identificador_lote)

    curated_dir = Path(curated_dir)
    curated_dir.mkdir(parents=True, exist_ok=True)
    arquivo_relatorio = curated_dir / f"curated_reconciliation_report_{identificador_lote}.parquet"
    arquivo_indice = curated_dir / f"curated_exception_index_{identificador_lote}.parquet"
    relatorio.to_parquet(arquivo_relatorio, index=False)
    indice_excecoes.to_parquet(arquivo_indice, index=False)
    entidades_reprovadas = relatorio.loc[relatorio["status"].eq("failed"), "entity"].tolist()
    return {
        "arquivo_relatorio": arquivo_relatorio,
        "arquivo_indice_excecoes": arquivo_indice,
        "quality_passed": not entidades_reprovadas,
        "entidades_reprovadas": entidades_reprovadas,
        "manifesto": {
            "batch_id": identificador_lote,
            "thresholds": {
                "min_match_rate": limiares.min_match_rate,
                "financial_tolerance": str(limiares.financial_tolerance),
            },
            "quality_passed": not entidades_reprovadas,
            "failed_entities": entidades_reprovadas,
            "reconciliation_report_rows": len(relatorio),
            "exception_index_rows": len(indice_excecoes),
        },
    }
